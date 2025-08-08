from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTableView,
    QTreeView,
)
from PySide6.QtCore import Signal, Qt, QModelIndex

from specter.client import Client

from specter_viewer.models.objects import GRPCObjectsModel


class ObjectsDock(QDockWidget):
    current_object_changed = Signal(str)

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
        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self):
        selected_indexes = self._view.selectionModel().selectedIndexes()
        selected_index = selected_indexes[0] if selected_indexes else QModelIndex()

        object_id = None
        if selected_index.isValid():
            object_id = self._model.data(
                selected_index.sibling(
                    selected_index.row(), GRPCObjectsModel.Columns.Id
                ),
                Qt.ItemDataRole.DisplayRole,
            )

        self.current_object_changed.emit(object_id)
