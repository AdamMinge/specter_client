import typing
import re


class CodeGenerator:
    def __init__(self):
        self._object_vars: dict[str, str] = {}
        self._event_mapping = {
            "context_menu_opened": self._context_menu_opened,
            "button_clicked": self._button_clicked,
            "button_toggled": self._button_toggled,
            "combo_box_current_changed": self._combo_box_current_changed,
            "spin_box_value_changed": self._spin_box_value_changed,
            "double_spin_box_value_changed": self._double_spin_box_value_changed,
            "slider_value_changed": self._slider_value_changed,
            "tab_current_changed": self._tab_current_changed,
            "tab_closed": self._tab_closed,
            "tab_moved": self._tab_moved,
            "tool_box_current_changed": self._tool_box_current_changed,
            "action_triggered": self._action_triggered,
            "text_edit_text_changed": self._text_edit_text_changed,
            "line_edit_text_changed": self._line_edit_text_changed,
            "line_edit_return_pressed": self._line_edit_return_pressed,
        }

    @staticmethod
    def _get_id_key(inner_event: typing.Any) -> str:
        try:
            qq = getattr(inner_event, "object_id", None)
            if qq is None:
                return ""
            return str(qq.id)
        except Exception:
            return ""

    @staticmethod
    def _normalize(events: list[typing.Any]) -> list[typing.Any]:
        if not events:
            return []

        out: list[typing.Any] = []
        for ev in events:
            which = ev.WhichOneof("event")
            if not which:
                continue
            inner = getattr(ev, which)

            if not out:
                out.append(ev)
                continue

            last = out[-1]
            last_which = last.WhichOneof("event")
            last_inner = getattr(last, last_which)

            last_id = CodeGenerator._get_id_key(last_inner)
            cur_id = CodeGenerator._get_id_key(inner)

            text_group = {"text_edit_text_changed", "line_edit_text_changed"}
            if (
                which in text_group
                and which == last_which
                and last_id
                and last_id == cur_id
            ):
                setattr(last_inner, "value", inner.value)
                continue

            numeric_group = {
                "combo_box_current_changed",
                "spin_box_value_changed",
                "double_spin_box_value_changed",
                "slider_value_changed",
                "tab_current_changed",
                "tool_box_current_changed",
            }
            if (
                which in numeric_group
                and which == last_which
                and last_id
                and last_id == cur_id
            ):
                for fld in ("index", "value", "from", "to"):
                    if hasattr(inner, fld):
                        setattr(last_inner, fld, getattr(inner, fld))
                continue

            out.append(ev)

        return out

    @staticmethod
    def _wrap(action: str, code: str, width: int = 80) -> str:
        text = f" {action} "
        header = text.center(width, "#")
        footer = "#" * width
        return f"{header}\n{code}{footer}\n\n"

    def _get_or_declare_object(self, event: typing.Any) -> tuple[str, str]:
        q = event.object_query.query.replace("'", "\\'")
        obj_id = getattr(event, "object_id", None)
        key = str(obj_id.id) if obj_id and getattr(obj_id, "id", None) else q

        if key in self._object_vars:
            return self._object_vars[key], ""

        name = f"obj_{getattr(obj_id, "id", None)}"
        candidate = name
        suffix = 1
        while candidate in self._object_vars.values():
            candidate = f"{name}_{suffix}"
            suffix += 1

        self._object_vars[key] = candidate
        code_prefix = f"{candidate} = m.waitForObject('{q}')\n"
        return candidate, code_prefix

    def _context_menu_opened(self, event: typing.Any) -> str:  # TODO: Implement
        var_name, prefix = self._get_or_declare_object(event)
        code = f"{prefix}"
        return self._wrap("context menu opened", code)

    def _button_clicked(self, event: typing.Any) -> str:
        var_name, prefix = self._get_or_declare_object(event)
        code = f"{prefix}" f"{var_name}.click()\n"
        return self._wrap("button clicked", code)

    def _button_toggled(self, event: typing.Any) -> str:
        var_name, prefix = self._get_or_declare_object(event)
        checked = bool(event.checked)
        code = f"{prefix}" f"{var_name}.setChecked({checked})\n"
        return self._wrap("button toggled", code)

    def _combo_box_current_changed(self, event: typing.Any) -> str:
        var_name, prefix = self._get_or_declare_object(event)
        idx = int(event.index)
        code = f"{prefix}" f"{var_name}.setCurrentIndex({idx})\n"
        return self._wrap("combobox current changed", code)

    def _spin_box_value_changed(self, event: typing.Any) -> str:
        var_name, prefix = self._get_or_declare_object(event)
        v = int(event.value)
        code = f"{prefix}" f"{var_name}.setValue({v})\n"
        return self._wrap("spinbox value changed", code)

    def _double_spin_box_value_changed(self, event: typing.Any) -> str:
        var_name, prefix = self._get_or_declare_object(event)
        v = float(event.value)
        code = f"{prefix}" f"{var_name}.setValue({v})\n"
        return self._wrap("doublespinbox value changed", code)

    def _slider_value_changed(self, event: typing.Any) -> str:
        var_name, prefix = self._get_or_declare_object(event)
        v = int(event.value)
        code = f"{prefix}" f"{var_name}.setValue({v})\n"
        return self._wrap("slider value changed", code)

    def _tab_current_changed(self, event: typing.Any) -> str:
        var_name, prefix = self._get_or_declare_object(event)
        idx = int(event.index)
        code = f"{prefix}" f"{var_name}.setCurrentIndex({idx})\n"
        return self._wrap("tab current changed", code)

    def _tab_closed(self, event: typing.Any) -> str:  # TODO: Implement
        var_name, prefix = self._get_or_declare_object(event)
        idx = int(event.index)
        code = f"{prefix}"
        return self._wrap("tab closed", code)

    def _tab_moved(self, event: typing.Any) -> str:  # TODO: Implement
        var_name, prefix = self._get_or_declare_object(event)
        frm = int(getattr(event, "from"))
        to = int(event.to)
        code = f"{prefix}"
        return self._wrap("tab moved", code)

    def _tool_box_current_changed(self, event: typing.Any) -> str:
        var_name, prefix = self._get_or_declare_object(event)
        idx = int(event.index)
        code = f"{prefix}" f"{var_name}.setCurrentIndex({idx})\n"
        return self._wrap("toolbox current changed", code)

    def _action_triggered(self, event: typing.Any) -> str:
        var_name, prefix = self._get_or_declare_object(event)
        code = f"{prefix}" f"{var_name}.trigger()\n"
        return self._wrap("action triggered", code)

    def _text_edit_text_changed(self, event: typing.Any) -> str:
        var_name, prefix = self._get_or_declare_object(event)
        value = event.value.replace("'", "\\'")
        code = f"{prefix}" f"{var_name}.setText('{value}')\n"
        return self._wrap("textedit text changed", code)

    def _line_edit_text_changed(self, event: typing.Any) -> str:
        var_name, prefix = self._get_or_declare_object(event)
        value = event.value.replace("'", "\\'")
        code = f"{prefix}" f"{var_name}.setText('{value}')\n"
        return self._wrap("lineedit text changed", code)

    def _line_edit_return_pressed(self, event: typing.Any) -> str:  # TODO: Implement
        var_name, prefix = self._get_or_declare_object(event)
        code = f"{prefix}"
        return self._wrap("lineedit return pressed", code)

    def generate(self, events: list[typing.Any]) -> str:
        script_text = ""
        normalized = self._normalize(events)

        for event in normalized:
            which = event.WhichOneof("event")
            assert which, "event must have an inner oneof set"
            handler = self._event_mapping.get(which)
            if not handler:
                script_text += f"# Skipping unsupported event: {which}\n"
                continue
            inner = getattr(event, which)
            try:
                script_text += f"{handler(inner)}\n"
            except Exception as exc:
                script_text += f"# Error generating code for event {which}: {exc}\n"

        return script_text
