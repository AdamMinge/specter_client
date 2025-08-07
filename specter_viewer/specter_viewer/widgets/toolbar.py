from PySide6.QtWidgets import (
    QToolBar,
)
from PySide6.QtGui import QIcon, QPixmap, QAction

from google.protobuf import empty_pb2

from specter.client import Client


class ToolBar(QToolBar):
    def __init__(self, client: Client):
        super().__init__()
        self._client = client
        self._init_ui()
        self._init_connnection()
        self.setWindowTitle("Tools")

    def _init_ui(self):
        self._action_grid_view = QAction(
            QIcon(QPixmap(":/icons/select.png")), "Toggle Marker", self
        )
        self._action_grid_view.setCheckable(True)
        self._action_grid_view.setStatusTip(
            "Toggle the visibility of the marker in the specteted app"
        )

        self.addAction(self._action_grid_view)

    def _init_connnection(self):
        self._action_grid_view.triggered.connect(self._on_marker_toggled)

    def _on_marker_toggled(self, toggled: bool):
        if toggled:
            self._client.marker_stub.Start(empty_pb2.Empty())
        else:
            self._client.marker_stub.Stop(empty_pb2.Empty())
