from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTableView,
    QTreeView,
)
from PySide6.QtCore import Signal, Qt, QModelIndex

from specterui.client import Client

from specterui.models import (
    GRPCObjectsModel,
)


class ObjectsDock(QDockWidget):
    selected_object = Signal(str)

    def __init__(self, client: Client):
        super().__init__("Objects")
        self._client = client
        self._init_ui()
        self._init_connection()

    def _init_ui(self):
        self._model = GRPCObjectsModel(self._client)
        self._view = QTreeView()
        self._view.setModel(self._model)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setAlternatingRowColors(True)

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self._view)
        container.setLayout(layout)
        self.setWidget(container)

    def _init_connection(self):
        self._view.selectionModel().currentChanged.connect(self._on_selection_changed)
        self._model.dataChanged.connect(self._on_data_changed)

    def _on_selection_changed(self, current: QModelIndex, _: QModelIndex):
        query = None
        if current.isValid():
            query = self._model.data(
                current.sibling(current.row(), GRPCObjectsModel.Columns.Query),
                Qt.ItemDataRole.UserRole,
            )

        self.selected_object.emit(query)

    def _on_data_changed(
        self, topLeft: QModelIndex, bottomRight: QModelIndex, roles=None
    ):
        current_index = self._view.currentIndex()

        if not current_index.isValid():
            return

        if current_index.parent() != topLeft.parent():
            return

        if (
            topLeft.row() <= current_index.row() <= bottomRight.row()
            and topLeft.column() <= current_index.column() <= bottomRight.column()
        ):

            query = self._model.data(
                current_index.sibling(
                    current_index.row(), GRPCObjectsModel.Columns.Query
                ),
                Qt.ItemDataRole.UserRole,
            )

            self.selected_object.emit(query)
