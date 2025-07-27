import typing

from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTableView,
    QHeaderView,
)

from pyside6_utils.widgets import DataClassTreeView

from specterui.client import Client
from specterui.context import Context
from specterui.models import (
    GRPCPropertiesModel,
    FilteredPropertiesTypeProxyModel,
)


class PropertiesDock(QDockWidget):
    def __init__(self, client: Client, context: Context):
        super().__init__("Properties")
        self._client = client
        self._context = context
        self._init_ui()

    def _init_ui(self):
        self._model = GRPCPropertiesModel(self._client, self._context)
        self._proxy_model = FilteredPropertiesTypeProxyModel()
        self._proxy_model.setSourceModel(self._model)
        self._view = DataClassTreeView()
        self._view.setModel(self._proxy_model)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setAlternatingRowColors(True)
        self._view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._view.header().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self._view)
        container.setLayout(layout)
        self.setWidget(container)
