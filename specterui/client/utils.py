import typing

from google.protobuf.struct_pb2 import Value, Struct


def convert_from_value(value: Value) -> typing.Any:
    if value.HasField("string_value"):
        return value.string_value
    elif value.HasField("number_value"):
        return value.number_value
    elif value.HasField("bool_value"):
        return value.bool_value
    elif value.HasField("list_value"):
        return [convert_from_value(v) for v in value.list_value.values]
    elif value.HasField("struct_value"):
        fields = value.struct_value.fields

        if "_type" in fields:
            type_name = fields["_type"].string_value
            plain = {
                k: convert_from_value(v) for k, v in fields.items() if k != "_type"
            }

            return {"_type": type_name, **plain}

        return {k: convert_from_value(v) for k, v in fields.items()}

    return None


def convert_to_value(value: typing.Any) -> Value:
    v = Value()

    if isinstance(value, dict) and "_type" in value:
        qt_type = value["_type"]
        s = Struct()
        s.fields["_type"].string_value = qt_type

        for k, val in value.items():
            if k == "_type" or val is None:
                continue
            s.fields[k].CopyFrom(convert_to_value(val))

        v.struct_value.CopyFrom(s)
        return v

    if isinstance(value, bool):
        v.bool_value = value
    elif isinstance(value, (int, float)):
        v.number_value = float(value)
    elif isinstance(value, str):
        v.string_value = value
    elif isinstance(value, list):
        v.list_value.values.extend(
            [convert_to_value(i) for i in value if i is not None]
        )
    elif isinstance(value, dict):
        s = Struct()
        for k, val in value.items():
            if val is not None:
                s.fields[k].CopyFrom(convert_to_value(val))
        v.struct_value.CopyFrom(s)
    else:
        return Value()

    return v
