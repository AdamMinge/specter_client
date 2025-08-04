import typing

from PySide6.QtCore import Qt

from pyside6_utils.models.console_widget_models.console_model import BaseConsoleItem

from google.protobuf import empty_pb2

from specter.client import Client, StreamReader


class GRPCRecorderConsoleItem(BaseConsoleItem):
    def __init__(self, id: str, client: Client, parent=None):
        super().__init__(parent)
        self._id = id
        self._lines = []
        self._client = client
        self._stream_reader = None

    def get_current_line_list(self) -> typing.Tuple[list[str], int]:
        return self._lines, 0

    def data(self, role: Qt.ItemDataRole, column: int = 0) -> typing.Any:
        if role == Qt.ItemDataRole.DisplayRole:
            return self._id
        else:
            return None
        
    def start(self):
        if not self._stream_reader:
            self._stream_reader = StreamReader(
                stream=self._client.recorder_stub.ListenCommands(empty_pb2.Empty()),
                on_data=self.handle_recorded_action
            )

    def stop(self):
        if self._stream_reader:
            self._stream_reader.stop()
            self._stream_reader = None

    def is_running(self) -> bool:
        return self._stream_reader is not None
    
    def handle_recorded_action(self, action):
        commands = [action.command]
        self._lines.extend(commands)
        self.loadedLinesChanged.emit(commands, len(self._lines))