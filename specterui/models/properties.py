import typing
import threading
import dataclasses

from pyside6_utils.models import DataclassModel

from specterui.proto.specter_pb2 import Object

from specterui.client import Client

class ObservableDict(dict):
    def __init__(self, *args, on_change=None, skip_set=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.__on_change = on_change
        self.__skip_set = skip_set

    def __setitem__(self, key, value):
        old_value = self.get(key, None)
        if old_value != value:
            self.__super_setitem__(key, value)
            if self.__on_change:
                self.__on_change(key, old_value, value)
        else:
            self.__super_setitem__(key, value)
    
    def __super_setitem__(self, key, value):
        if not self.__skip_set:
            super().__setitem__(key, value)


class GRPCPropertiesModel(DataclassModel):
    EmptyDataclass = dataclasses.make_dataclass("EmptyDataclass", [])

    def __init__(self, client: Client, parent=None):
        super().__init__(GRPCPropertiesModel.EmptyDataclass(), parent)

        self._client = client
        self.set_object(None)

        self._watch_thread = threading.Thread(
            target=self.handle_properties_changes, daemon=True
        )
        self._watch_thread.start()

    def fetch_initial_state(self):
        if self._object == None:
            self.set_dataclass_instance(GRPCPropertiesModel.EmptyDataclass())
            return

        response = self._client.object_stub.GetProperties(Object(query=self._object))

        fields = []
        values = {}

        for prop in response.properties:
            field_name = prop.property
            field_value = self.convert_value(prop.value)
            if field_value == None:
                continue

            field_type = type(field_value)

            if isinstance(field_value, (list, dict, set)):
                fields.append(
                    (
                        field_name,
                        field_type,
                        dataclasses.field(default_factory=lambda: field_value),
                    )
                )
            else:
                fields.append(
                    (field_name, field_type, dataclasses.field(default=field_value))
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
        pass

    def handle_properties_changes(self):
        pass

    def set_object(self, query: typing.Optional[str]):
        self._object = query
        self.fetch_initial_state()

    def convert_value(self, value):
        if value.HasField("string_value"):
            return value.string_value
        elif value.HasField("number_value"):
            return value.number_value
        elif value.HasField("bool_value"):
            return value.bool_value
        elif value.HasField("list_value"):
            return [self._convert_value(v) for v in value.list_value.values]
        elif value.HasField("struct_value"):
            return {
                k: self._convert_value(v) for k, v in value.struct_value.fields.items()
            }
        return None
