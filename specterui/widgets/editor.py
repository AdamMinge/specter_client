from PySide6.QtWidgets import QDockWidget

from specterui.client import Client


class EditorDock(QDockWidget):
    def __init__(self, client: Client):
        super().__init__("Editor")
        self._client = client
