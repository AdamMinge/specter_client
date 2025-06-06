import typing
import dataclasses

from PySide6.QtCore import (
    Qt,
    QMetaObject,
    Slot,
    Q_ARG,
    QModelIndex
)
from pyside6_utils.models import DataclassModel

from specterui.proto.specter_pb2 import Object, PropertyUpdate
from specterui.client import Client, StreamReader, convert_to_value, convert_from_value

class ObservableDict(dict):
    def __init__(self, *args, on_change=None, skip_set=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.__on_change = on_change
        self.__skip_set = skip_set

    def __setitem__(self, key, value):
        old_value = self.get(key, None)

        if not self.__skip_set:
            self._super_setitem(key, value)

        if old_value != value and self.__on_change:
            self.__on_change(key, old_value, value)

    def _super_setitem(self, key, value):
        super().__setitem__(key, value)


class GRPCPropertiesModel(DataclassModel):
    EmptyDataclass = dataclasses.make_dataclass('EmptyDataclass', [])

    def __init__(self, client: Client, parent=None):
        super().__init__(GRPCPropertiesModel.EmptyDataclass(), parent)

        self._client = client
        self._stream_reader = None
        self.set_object(None)

    def fetch_initial_state(self):
        if self._object is None:
            self.set_dataclass_instance(GRPCPropertiesModel.EmptyDataclass())
            return

        response = self._client.object_stub.GetProperties(Object(query=self._object))

        fields = []
        values = {}

        for prop in response.properties:
            base_path = prop.property
            base_value = convert_from_value(prop.value)
            editable = not prop.read_only

            if base_value is None:
                continue

            self.flatten_dict_field(
                fields,
                values,
                base_value,
                base_path,
                field_prefix=base_path,
                editable=editable
            )

        dataclass_instance = self.create_properties_dataclass(fields, values)
        self.set_dataclass_instance(dataclass_instance)

    def create_properties_dataclass(self, fields: list[typing.Any], values: dict[typing.Any]):
        DynamicPropertiesDataclass = dataclasses.make_dataclass(
            "DynamicProperties", fields
        )

        dataclass_instance = DynamicPropertiesDataclass(**values)

        observed_dict = ObservableDict(dataclass_instance.__dict__, on_change=self.change_property)
        object.__setattr__(dataclass_instance, '__dict__', observed_dict)

        return dataclass_instance
    
    def flatten_dict_field(self, fields: list, values: dict, current_value: typing.Any, full_path: str, field_prefix: str, editable: bool):
        display_path = '/'.join(full_path.split('/')[:-1])
        display_name = field_prefix.split('_')[-1]

        metadata = {
            "editable": editable,
            "display_name": display_name,
        }
        if display_path:
            metadata["display_path"] = f"{display_path}"

        if isinstance(current_value, dict):
            for key, sub_value in current_value.items():
                sub_prefix = f"{field_prefix}_{key}" if field_prefix else key
                sub_path = f"{full_path}/{key}" if full_path else key
                self.flatten_dict_field(fields, values, sub_value, sub_path, sub_prefix, editable)
        elif isinstance(current_value, (list, set)):
            fields.append(
                (field_prefix, type(current_value), dataclasses.field(default_factory=lambda: current_value, metadata=metadata))
            )
            values[field_prefix] = current_value
        else:
            fields.append(
                (field_prefix, type(current_value), dataclasses.field(default=current_value, metadata=metadata))
            )
            values[field_prefix] = current_value
    
    def change_property(self, field_name: str, old_value: typing.Any, new_value: typing.Any):
        instance = self.get_dataclass()
        observed_dict: ObservableDict = getattr(instance, '__dict__')
        root_field = field_name.split('_', 1)[0]
        
        nested_items = {
            k[len(root_field) + 1:]: (new_value if k == field_name else v)
            for k, v in observed_dict.items()
            if k == root_field or k.startswith(f"{root_field}_")
        }

        def nest(keys: list[str], val):
            if not keys:
                return val
            return {keys[0]: nest(keys[1:], val)}

        merged = {}
        for key, val in nested_items.items():
            keys = key.split('_') if key else []
            sub_tree = nest(keys, val)

            def deep_merge(target, src):
                for k, v in src.items():
                    if isinstance(v, dict) and k in target and isinstance(target[k], dict):
                        deep_merge(target[k], v)
                    else:
                        target[k] = v

            deep_merge(merged, sub_tree)

        self._client.object_stub.UpdateProperty(
            PropertyUpdate(
                object=Object(query=self._object),
                property=root_field,
                value=convert_to_value(merged)
            )
        )

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
        observed_dict: ObservableDict = getattr(instance, '__dict__')
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
                self.dataChanged.emit(self.index(index.row(), 0, index.parent()), self.index(index.row(), 1, index.parent()))

    def set_object(self, query: typing.Optional[str]):
        self._object = query
        self.fetch_initial_state()

        if self._stream_reader:
            self._stream_reader.stop()

        if self._object is not None:
            self._stream_reader = StreamReader(
                stream=self._client.object_stub.ListenPropertiesChanges(Object(query=self._object)),
                on_data=self.handle_properties_changes
            )
        else:
            self._stream_reader = None
    
    def find_index(self, property_name: str, parent: QModelIndex = QModelIndex()) -> QModelIndex | None:
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
