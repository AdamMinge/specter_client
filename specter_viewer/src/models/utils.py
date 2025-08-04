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


def flatten_dict_field(
    current_value: typing.Any,
    full_path: str,
    field_prefix: str,
    editable: bool,
) -> set[list, dict]:
    fields = []
    values = {}

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
            sub_fields, sub_values = flatten_dict_field(
                sub_value, sub_path, sub_prefix, editable
            )
            fields.extend(sub_fields)
            values.update(sub_values)

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

    return (fields, values)


def _nest_keys(keys: list[str], val: typing.Any) -> typing.Any:
    if not keys:
        return val
    return {keys[0]: _nest_keys(keys[1:], val)}


def _deep_merge(target: typing.Any, src: typing.Any) -> typing.Any:
    if isinstance(target, dict) and isinstance(src, dict):
        for k, v in src.items():
            if k in target and isinstance(target[k], dict) and isinstance(v, dict):
                target[k] = _deep_merge(target[k], v)
            else:
                target[k] = v
        return target
    else:
        return src


def _flatten_dict(d: dict, parent_key: str = "", sep: str = "_") -> dict:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _build_unflattened_single_root_field(
    instance: typing.Any, root_field_name: str
) -> typing.Any:
    instance_dict = getattr(instance, "__dict__")
    initial_root_value = getattr(instance, root_field_name, {})

    if isinstance(initial_root_value, dict):
        unflattened_result = _deep_merge({}, initial_root_value)
    else:
        unflattened_result = initial_root_value

    for attr_name, attr_value in instance_dict.items():
        if attr_name.startswith(f"{root_field_name}_"):
            nested_path_str = attr_name[len(root_field_name) + 1 :]

            if not isinstance(unflattened_result, dict):
                unflattened_result = {}

            keys_list = nested_path_str.split("_")
            sub_tree_from_flat_attr = _nest_keys(keys_list, attr_value)

            unflattened_result = _deep_merge(
                unflattened_result, sub_tree_from_flat_attr
            )

    return unflattened_result


def unflatten_dict_field(
    dataclass_instance: typing.Any,
    root_field_to_flatten: str,
    updates: list[tuple[str, typing.Any]] = [],
) -> typing.Any:
    unflattened_target_field = _build_unflattened_single_root_field(
        dataclass_instance, root_field_to_flatten
    )

    temp_unflattened_container = {"_value": unflattened_target_field}

    for field_name, new_value in updates:
        if field_name == root_field_to_flatten:
            temp_unflattened_container["_value"] = _deep_merge(
                temp_unflattened_container["_value"], new_value
            )
        elif field_name.startswith(f"{root_field_to_flatten}_"):
            if not isinstance(temp_unflattened_container["_value"], dict):
                temp_unflattened_container["_value"] = {}

            nested_path_str = field_name[len(root_field_to_flatten) + 1 :]
            keys_list = nested_path_str.split("_")

            override_subtree = _nest_keys(keys_list, new_value)

            temp_unflattened_container["_value"] = _deep_merge(
                temp_unflattened_container["_value"], override_subtree
            )

    final_unflattened_target_field = temp_unflattened_container["_value"]

    if isinstance(final_unflattened_target_field, dict):
        final_flattened_dict = _flatten_dict(final_unflattened_target_field)
        return final_flattened_dict
    else:
        return final_unflattened_target_field
