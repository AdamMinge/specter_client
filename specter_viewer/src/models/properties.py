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

from specter.proto.specter_pb2 import ObjectId, PropertyUpdate
from specter.client import Client, StreamReader, convert_to_value, convert_from_value

from specter_viewer.models.utils import (
    ObservableDict,
    EmptyDataclass,
    flatten_dict_field,
    unflatten_dict_field,
    create_properties_dataclass,
)


class GRPCPropertiesModel(DataclassModel):
    def __init__(self, client: Client, parent=None):
        super().__init__(EmptyDataclass(), parent)

        self._client = client
        self._stream_reader = None
        self._object_id = None

    def set_object(self, object_id: str):
        self._object_id = object_id

        self._fetch_initial_state()

        if self._stream_reader:
            self._stream_reader.stop()

        if self._object_id is not None:
            self._stream_reader = StreamReader(
                stream=self._client.object_stub.ListenPropertiesChanges(
                    ObjectId(id=self._object_id)
                ),
                on_data=self._handle_properties_changes,
            )
        else:
            self._stream_reader = None

    def _fetch_initial_state(self) -> bool:
        if self._object_id is None:
            self.set_dataclass_instance(EmptyDataclass())
            return False

        try:
            response = self._client.object_stub.GetProperties(
                ObjectId(id=self._object_id)
            )
        except Exception:
            self.set_dataclass_instance(EmptyDataclass())
            return False

        fields = []
        values = {}

        for prop in response.properties:
            base_path = prop.property_name
            base_value = convert_from_value(prop.value)
            editable = not prop.read_only

            if base_value is None:
                continue

            prop_fields, prop_values = flatten_dict_field(
                base_value,
                base_path,
                field_prefix=base_path,
                editable=editable,
            )
            fields.extend(prop_fields)
            values.update(prop_values)

        dataclass_instance = create_properties_dataclass(
            fields, values, self._change_property
        )
        self.set_dataclass_instance(dataclass_instance)
        return True

    def _change_property(
        self, field_name: str, old_value: typing.Any, new_value: typing.Any
    ):
        root_field = field_name.split("_", 1)[0]
        value_to_send = unflatten_dict_field(
            self.get_dataclass(), root_field, [(field_name, new_value)]
        )

        self._client.object_stub.UpdateProperty(
            PropertyUpdate(
                object_id=ObjectId(id=self._object_id),
                property_name=root_field,
                value=convert_to_value(value_to_send),
            )
        )

    def _handle_properties_changes(self, change):
        if change.HasField("added"):
            QMetaObject.invokeMethod(
                self,
                "_handle_property_added",
                Qt.QueuedConnection,
                Q_ARG(str, change.added.property_name),
                Q_ARG("QVariant", change.added.value),
            )
        elif change.HasField("removed"):
            QMetaObject.invokeMethod(
                self,
                "_handle_property_removed",
                Qt.QueuedConnection,
                Q_ARG(str, change.removed.property_name),
            )
        elif change.HasField("updated"):
            QMetaObject.invokeMethod(
                self,
                "_handle_property_updated",
                Qt.QueuedConnection,
                Q_ARG(str, change.updated.property_name),
                Q_ARG("QVariant", change.updated.old_value),
                Q_ARG("QVariant", change.updated.new_value),
            )

    @Slot(str, "QVariant")
    def _handle_property_added(self, property, value):
        pass

    @Slot(str, "QVariant")
    def _handle_property_removed(self, property):
        pass

    @Slot(str, "QVariant", "QVariant")
    def _handle_property_updated(self, property, old_value, new_value):
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
                index = self._find_index(k)
                observed_dict._super_setitem(k, v)
                self.dataChanged.emit(
                    self.index(index.row(), 0, index.parent()),
                    self.index(index.row(), 1, index.parent()),
                )

    def _find_index(
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

            child_index = self._find_index(property_name, parent=index)
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
