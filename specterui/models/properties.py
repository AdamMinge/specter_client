import typing

from PySide6.QtCore import (
    Qt,
    QMetaObject,
    Slot,
    Q_ARG,
    QModelIndex,
    QSortFilterProxyModel,
)

from pyside6_utils.models import DataclassModel

from specterui.proto.specter_pb2 import Object, PropertyUpdate
from specterui.client import Client, StreamReader, convert_to_value, convert_from_value
from specterui.models.utils import (
    ObservableDict,
    EmptyDataclass,
    flatten_dict_field,
    create_properties_dataclass,
)


class GRPCPropertiesModel(DataclassModel):
    def __init__(self, client: Client, parent=None):
        super().__init__(EmptyDataclass(), parent)

        self._client = client
        self._stream_reader = None
        self.set_object(None)

    def fetch_initial_state(self) -> bool:
        if self._object is None:
            self.set_dataclass_instance(EmptyDataclass())
            return False

        try:
            response = self._client.object_stub.GetProperties(
                Object(query=self._object)
            )
        except Exception:
            self.set_dataclass_instance(EmptyDataclass())
            return False

        fields = []
        values = {}

        for prop in response.properties:
            base_path = prop.name
            base_value = convert_from_value(prop.value)
            editable = not prop.read_only

            if base_value is None:
                continue

            flatten_dict_field(
                fields,
                values,
                base_value,
                base_path,
                field_prefix=base_path,
                editable=editable,
            )

        dataclass_instance = create_properties_dataclass(
            fields, values, self.change_property
        )
        self.set_dataclass_instance(dataclass_instance)
        return True

    def change_property(
        self, field_name: str, old_value: typing.Any, new_value: typing.Any
    ):
        instance = self.get_dataclass()
        observed_dict: ObservableDict = getattr(instance, "__dict__")
        root_field = field_name.split("_", 1)[0]

        if field_name == root_field:
            value_to_send = self.build_root_value(new_value)
        else:
            value_to_send = self.build_nested_value(
                field_name, root_field, new_value, observed_dict
            )

        self._client.object_stub.UpdateProperty(
            PropertyUpdate(
                object=Object(query=self._object),
                property=root_field,
                value=convert_to_value(value_to_send),
            )
        )

    def build_root_value(self, value: typing.Any) -> typing.Any:
        return value

    def build_nested_value(
        self,
        field_name: str,
        root_field: str,
        new_value: typing.Any,
        observed_dict: dict,
    ) -> dict:
        nested_items = {
            k[len(root_field) + 1 :]: (new_value if k == field_name else v)
            for k, v in observed_dict.items()
            if k.startswith(f"{root_field}_")
        }

        merged = {}
        for key, val in nested_items.items():
            keys = key.split("_") if key else []
            sub_tree = self.nest_keys(keys, val)
            self.deep_merge(merged, sub_tree)

        return merged

    def nest_keys(self, keys: list[str], val: typing.Any) -> dict:
        if not keys:
            return val
        return {keys[0]: self.nest_keys(keys[1:], val)}

    def deep_merge(self, target: dict, src: dict) -> None:
        for k, v in src.items():
            if isinstance(v, dict) and k in target and isinstance(target[k], dict):
                self.deep_merge(target[k], v)
            else:
                target[k] = v

    def handle_properties_changes(self, change):
        if change.HasField("added"):
            QMetaObject.invokeMethod(
                self,
                "handle_property_added",
                Qt.QueuedConnection,
                Q_ARG(str, change.added.property),
                Q_ARG("QVariant", change.added.value),
            )
        elif change.HasField("removed"):
            QMetaObject.invokeMethod(
                self,
                "handle_property_removed",
                Qt.QueuedConnection,
                Q_ARG(str, change.removed.property),
            )
        elif change.HasField("updated"):
            QMetaObject.invokeMethod(
                self,
                "handle_property_updated",
                Qt.QueuedConnection,
                Q_ARG(str, change.updated.property),
                Q_ARG("QVariant", change.updated.old_value),
                Q_ARG("QVariant", change.updated.new_value),
            )

    @Slot(str, "QVariant")
    def handle_property_added(self, property, value):
        pass

    @Slot(str, "QVariant")
    def handle_property_removed(self, property):
        pass

    @Slot(str, "QVariant", "QVariant")
    def handle_property_updated(self, property, old_value, new_value):
        instance = self.get_dataclass()
        observed_dict: ObservableDict = getattr(instance, "__dict__")
        updated_value = convert_from_value(new_value)

        def flatten(prefix: str, value):
            result = {}
            if isinstance(value, dict):
                for k, v in value.items():
                    nested = flatten(f"{prefix}_{k}" if prefix else k, v)
                    result.update(nested)
            else:
                result[prefix] = value
            return result

        flat_updates = flatten(property, updated_value)

        for k, v in flat_updates.items():
            if k in observed_dict:
                index = self.find_index(k)
                observed_dict._super_setitem(k, v)
                self.dataChanged.emit(
                    self.index(index.row(), 0, index.parent()),
                    self.index(index.row(), 1, index.parent()),
                )

    def set_object(self, query: typing.Optional[str]):
        self._object = query
        self.fetch_initial_state()

        if self._stream_reader:
            self._stream_reader.stop()

        if self._object is not None:
            self._stream_reader = StreamReader(
                stream=self._client.object_stub.ListenPropertiesChanges(
                    Object(query=self._object)
                ),
                on_data=self.handle_properties_changes,
            )
        else:
            self._stream_reader = None

    def find_index(
        self, property_name: str, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex | None:
        for row in range(self.rowCount(parent)):
            index = self.index(row, 0, parent)
            if not index.isValid():
                continue

            field = index.data(DataclassModel.CustomDataRoles.FieldRole)
            if field is not None:
                if field.name == property_name:
                    return index

            child_index = self.find_index(property_name, parent=index)
            if child_index is not None:
                return child_index

        return None


class FilteredPropertiesTypeProxyModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        source_model = self.sourceModel()
        index = source_model.index(source_row, 0, source_parent)
        if not index.isValid():
            return True

        field_name = index.data(DataclassModel.CustomDataRoles.AttributeNameRole)
        return not (isinstance(field_name, str) and field_name.endswith("type"))
