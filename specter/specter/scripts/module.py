import time

from PySide6.QtCore import Qt, QPoint

from specter.proto.specter_pb2 import (
    ObjectSearchQuery,
    MouseEvent,
    Offset,
    CursorMove,
    WheelScroll,
    TextInput,
    MouseButton,
    KeyEvent,
)

from specter.client import Client
from specter.scripts.wrappers import ObjectWrapper


class ScriptModule:
    def __init__(self, client: Client):
        super().__init__()
        self._client: Client = client

    def _qt_button_to_proto(self, button: Qt.MouseButton) -> MouseButton:
        if button == Qt.MouseButton.LeftButton:
            return MouseButton.LEFT
        elif button == Qt.MouseButton.RightButton:
            return MouseButton.RIGHT
        elif button == Qt.MouseButton.MiddleButton:
            return MouseButton.MIDDLE
        else:
            raise ValueError(f"Unsupported Qt.MouseButton: {button}")

    def _build_key_event(self, key: Qt.Key, mods: Qt.KeyboardModifier) -> KeyEvent:
        return KeyEvent(
            key_code=int(key),
            ctrl=bool(mods & Qt.KeyboardModifier.ControlModifier),
            alt=bool(mods & Qt.KeyboardModifier.AltModifier),
            shift=bool(mods & Qt.KeyboardModifier.ShiftModifier),
            meta=bool(mods & Qt.KeyboardModifier.MetaModifier),
        )

    def waitForObject(self, object_query, timeout=10):
        object_pb_request = ObjectSearchQuery(query=object_query)

        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self._client.object_stub.Find(object_pb_request)

            if len(response.ids) == 1:
                found_object_pb = response.ids[0]
                return ObjectWrapper.create_wrapper_object(
                    self._client, found_object_pb.id
                )
            time.sleep(0.5)

        raise TimeoutError(
            f"Object matching query '{object_query}' not found within {timeout} seconds."
        )

    def pressMouseButton(self, pos: QPoint, button: Qt.MouseButton, double_click: bool):
        event = MouseEvent(
            offset=Offset(x=pos.x(), y=pos.y()),
            button=self._qt_button_to_proto(button),
            double_click=double_click,
        )
        self._client.mouse_stub.PressButton(event)

    def releaseMouseButton(self, pos: QPoint, button: Qt.MouseButton):
        event = MouseEvent(
            offset=Offset(x=pos.x(), y=pos.y()),
            button=self._qt_button_to_proto(button),
        )
        self._client.mouse_stub.ReleaseButton(event)

    def clickMouseButton(self, pos: QPoint, button: Qt.MouseButton, double_click: bool):
        event = MouseEvent(
            offset=Offset(x=pos.x(), y=pos.y()),
            button=self._qt_button_to_proto(button),
            double_click=double_click,
        )
        self._client.mouse_stub.ClickButton(event)

    def moveCursor(self, pos: QPoint):
        move = CursorMove(offset=Offset(x=pos.x(), y=pos.y()))
        self._client.mouse_stub.MoveCursor(move)

    def scrollWheel(self, delta: QPoint):
        scroll = WheelScroll(delta_x=delta.x(), delta_y=delta.y())
        self._client.mouse_stub.ScrollWheel(scroll)

    def pressKey(
        self, key: Qt.Key, mods: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
    ):
        event = self._build_key_event(key, mods)
        self._client.keyboard_stub.PressKey(event)

    def releaseKey(
        self, key: Qt.Key, mods: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
    ):
        event = self._build_key_event(key, mods)
        self._client.keyboard_stub.ReleaseKey(event)

    def tapKey(
        self, key: Qt.Key, mods: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
    ):
        event = self._build_key_event(key, mods)
        self._client.keyboard_stub.TapKey(event)

    def enterText(self, text: str):
        self._client.keyboard_stub.EnterText(TextInput(text=text))
