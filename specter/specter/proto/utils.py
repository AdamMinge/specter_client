from PySide6.QtCore import Qt

from specter.proto.specter_pb2 import (
    MouseButton,
    KeyEvent,
)


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
