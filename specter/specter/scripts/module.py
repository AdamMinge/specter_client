import time
import typing

from PySide6.QtCore import Qt, QPoint

from specter.proto.utils import create_key_event, create_mouse_button, create_position
from specter.proto.specter_pb2 import (
    ObjectSearchQuery,
    MouseEvent,
    Offset,
    CursorMove,
    WheelScroll,
    TextInput,
    ObjectClick,
    ObjectId,
    ObjectHover,
    ObjectTextInput,
    Anchor,
)

from specter.client import Client
from specter.scripts.wrappers import ObjectWrapper


class ScriptModule:
    def __init__(self, client: Client):
        super().__init__()
        self._client: Client = client

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
            button=create_mouse_button(button),
            double_click=double_click,
        )
        self._client.mouse_stub.PressButton(event)

    def releaseMouseButton(self, pos: QPoint, button: Qt.MouseButton):
        event = MouseEvent(
            offset=Offset(x=pos.x(), y=pos.y()),
            button=create_mouse_button(button),
        )
        self._client.mouse_stub.ReleaseButton(event)

    def clickMouseButton(self, pos: QPoint, button: Qt.MouseButton, double_click: bool):
        event = MouseEvent(
            offset=Offset(x=pos.x(), y=pos.y()),
            button=create_mouse_button(button),
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
        event = create_key_event(key, mods)
        self._client.keyboard_stub.PressKey(event)

    def releaseKey(
        self, key: Qt.Key, mods: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
    ):
        event = create_key_event(key, mods)
        self._client.keyboard_stub.ReleaseKey(event)

    def tapKey(
        self, key: Qt.Key, mods: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
    ):
        event = create_key_event(key, mods)
        self._client.keyboard_stub.TapKey(event)

    def enterText(self, text: str):
        self._client.keyboard_stub.EnterText(TextInput(text=text))

    def clickObject(
        self,
        object: ObjectWrapper,
        pos_or_anchor: typing.Union[QPoint, Anchor, None],
        button: Qt.MouseButton,
        double_click: bool,
    ):
        event = ObjectClick(
            object_id=ObjectId(id=object._object_id),
            button=create_mouse_button(button),
            double_click=double_click,
            **create_position(pos_or_anchor),
        )
        self._client.mouse_stub.ClickOnObject(event)

    def hoverObject(
        self,
        object: ObjectWrapper,
        pos_or_anchor: typing.Union[QPoint, Anchor, None],
    ):
        event = ObjectHover(
            object_id=ObjectId(id=object.id), **create_position(pos_or_anchor)
        )
        self._client.mouse_stub.HoverOverObject(event)

    def enterTextIntoObject(self, object: ObjectWrapper, text: str):
        event = ObjectTextInput(
            object_id=ObjectId(id=object.id),
            text=text,
        )
        self._client.keyboard_stub.EnterTextIntoObject(event)
