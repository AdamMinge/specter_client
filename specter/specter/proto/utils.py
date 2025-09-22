import typing

from PySide6.QtCore import Qt, QPoint

from specter.proto.specter_pb2 import MouseButton, KeyEvent, Anchor, Offset


def create_mouse_button(button: Qt.MouseButton) -> MouseButton:
    if button == Qt.MouseButton.LeftButton:
        return MouseButton.LEFT
    elif button == Qt.MouseButton.RightButton:
        return MouseButton.RIGHT
    elif button == Qt.MouseButton.MiddleButton:
        return MouseButton.MIDDLE
    else:
        raise ValueError(f"Unsupported Qt.MouseButton: {button}")


def create_key_event(key: Qt.Key, mods: Qt.KeyboardModifier) -> KeyEvent:
    return KeyEvent(
        key_code=int(key),
        ctrl=bool(mods & Qt.KeyboardModifier.ControlModifier),
        alt=bool(mods & Qt.KeyboardModifier.AltModifier),
        shift=bool(mods & Qt.KeyboardModifier.ShiftModifier),
        meta=bool(mods & Qt.KeyboardModifier.MetaModifier),
    )


def create_position(
    pos_or_anchor: typing.Optional[typing.Union[QPoint, int]],
) -> typing.Dict[str, typing.Any]:
    if isinstance(pos_or_anchor, QPoint):
        return {"offset": Offset(x=pos_or_anchor.x(), y=pos_or_anchor.y())}
    elif isinstance(pos_or_anchor, int):
        if pos_or_anchor in Anchor.values():
            return {"anchor": pos_or_anchor}
        else:
            raise ValueError(f"Invalid Anchor value: {pos_or_anchor}")
    return {}
