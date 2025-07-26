import typing

from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTableView,
)

from specterui.client import Client


class MethodsDock(QDockWidget):
    def __init__(self, client: Client):
        super().__init__("Methods")
        self._client = client
        self._init_ui()

    def _init_ui(self):
        # self._model = GRPCMethodsModel(self._client)
        self._view = QTableView()
        # self._view.setModel(self._model)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setAlternatingRowColors(True)
        self._view.horizontalHeader().setHidden(True)

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self._view)
        container.setLayout(layout)
        self.setWidget(container)

    def set_object(self, query: typing.Optional[str]):
        pass
