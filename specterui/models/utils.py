import typing
import dataclasses

EmptyDataclass = dataclasses.make_dataclass("EmptyDataclass", [])


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


def flatten_dict_field(
    fields: list,
    values: dict,
    current_value: typing.Any,
    full_path: str,
    field_prefix: str,
    editable: bool,
):
    display_path = "/".join(full_path.split("/")[:-1])
    display_name = field_prefix.split("_")[-1]

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
            flatten_dict_field(
                fields, values, sub_value, sub_path, sub_prefix, editable
            )
    elif isinstance(current_value, (list, set)):
        fields.append(
            (
                field_prefix,
                type(current_value),
                dataclasses.field(
                    default_factory=lambda: current_value, metadata=metadata
                ),
            )
        )
        values[field_prefix] = current_value
    else:
        fields.append(
            (
                field_prefix,
                type(current_value),
                dataclasses.field(default=current_value, metadata=metadata),
            )
        )
        values[field_prefix] = current_value


def create_properties_dataclass(
    fields: list[typing.Any], values: dict[typing.Any], on_change=None
):
    if len(fields) == 0:
        return EmptyDataclass()

    DynamicPropertiesDataclass = dataclasses.make_dataclass("DynamicProperties", fields)

    dataclass_instance = DynamicPropertiesDataclass(**values)

    if on_change:
        observed_dict = ObservableDict(dataclass_instance.__dict__, on_change=on_change)
        object.__setattr__(dataclass_instance, "__dict__", observed_dict)

    return dataclass_instance
