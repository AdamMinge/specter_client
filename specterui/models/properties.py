import typing
import dataclasses

from PySide6.QtCore import (
    Qt,
    QMetaObject,
    Slot,
    Q_ARG,
)
from pyside6_utils.models import DataclassModel

from google.protobuf.struct_pb2 import Value

from specterui.proto.specter_pb2 import Object, PropertyUpdate
from specterui.client import Client, StreamReader

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
    EmptyDataclass = dataclasses.make_dataclass("EmptyDataclass", [])

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
            field_name = prop.property
            field_value = self.convert_from_value(prop.value)
            field_editable = not prop.read_only

            if field_value == None:
                continue

            field_type = type(field_value)
            metadata = {"editable": field_editable}

            if isinstance(field_value, (list, dict, set)):
                fields.append(
                    (
                        field_name,
                        field_type,
                        dataclasses.field(default_factory=lambda: field_value, metadata=metadata),
                    )
                )
            else:
                fields.append(
                    (field_name, field_type, dataclasses.field(default=field_value, metadata=metadata))
                )

            values[field_name] = field_value

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
    
    def change_property(self, field_name: str, old_value: typing.Any, new_value: typing.Any):
        self._client.object_stub.UpdateProperty(
            PropertyUpdate(
                object=Object(query=self._object), 
                property=field_name, 
                value=self.convert_to_value(new_value)
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
        index = self.find_index(property)
        if index is not None:
            instance = self.get_dataclass()
            observed_dict: ObservableDict = getattr(instance, '__dict__')
            observed_dict._super_setitem(property, self.convert_from_value(new_value))
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

    def convert_from_value(self, value: Value) -> typing.Any:
        if value.HasField("string_value"):
            return value.string_value
        elif value.HasField("number_value"):
            return value.number_value
        elif value.HasField("bool_value"):
            return value.bool_value
        elif value.HasField("list_value"):
            return [self.convert_from_value(v) for v in value.list_value.values]
        elif value.HasField("struct_value"):
            return {
                k: self.convert_from_value(v) for k, v in value.struct_value.fields.items()
            }
        return None
    
    def convert_to_value(self, value: typing.Any) -> Value:
        v = Value()
        if isinstance(value, bool):
            v.bool_value = value
        elif isinstance(value, (int, float)):
            v.number_value = float(value)
        elif isinstance(value, str):
            v.string_value = value
        else:
            return None
        return v
    
    def find_index(self, property_name: str):
        for row in range(self.rowCount()):
            index = self.index(row, 0)
            if index.data(Qt.ItemDataRole.DisplayRole) == property_name:
                return index
        return None
