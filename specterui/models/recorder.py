import typing

from PySide6.QtCore import Qt

from pyside6_utils.models.console_widget_models.console_model import BaseConsoleItem

from specterui.client import Client


class GRPCRecorderConsoleItem(BaseConsoleItem):
    def __init__(self, id: str, client: Client, parent=None):
        super().__init__(parent)
        self._id = id
        self._client = client

    def get_current_line_list(self) -> typing.Tuple[list[str], int]:
        return [], 0

    def data(self, role: Qt.ItemDataRole, column: int = 0):
        if role == Qt.ItemDataRole.DisplayRole:
            return self._id
        else:
            return None
        
    def start(self):
        pass

    def stop(self):
        pass

    def is_running(self):
        return False