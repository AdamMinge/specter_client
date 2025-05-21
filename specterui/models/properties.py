import typing
import threading
import dataclasses

from pyside6_utils.models import DataclassModel

from specterui.proto.specter_pb2 import Object

from specterui.client import Client


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

        DynamicPropertiesDataclass = dataclasses.make_dataclass(
            "DynamicProperties", fields
        )

        dataclass_instance = DynamicPropertiesDataclass(**values)
        self.set_dataclass_instance(dataclass_instance)

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
