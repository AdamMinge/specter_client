from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTableView,
    QTreeView,
    QLineEdit,
)
from PySide6.QtCore import (
    Qt,
    QModelIndex,
    QMetaObject,
    QItemSelectionModel,
    Signal,
    Slot,
    Q_ARG,
)

from google.protobuf import empty_pb2

from specter.client import Client, StreamReader

from specter_viewer.models.objects import GRPCObjectsModel
from specter_viewer.models.proxies import MultiColumnSortFilterProxyModel


class ObjectsDock(QDockWidget):
    current_object_changed = Signal(str)

    def __init__(self, client: Client):
        super().__init__("Objects")
        self._client = client
        self._init_ui()
        self._init_connection()
        self._init_selection_stream()

    def _init_ui(self):
        self._model = GRPCObjectsModel(self._client)
        self._proxy_model = MultiColumnSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.sort_by_columns(
            [GRPCObjectsModel.Columns.Name],
            [Qt.SortOrder.DescendingOrder],
        )
        self._proxy_model.set_filter_function("search_filter", self._search_filter)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search objects...")

        self._view = QTreeView()
        self._view.setModel(self._proxy_model)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setAlternatingRowColors(True)

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self._search)
        layout.addWidget(self._view)
        container.setLayout(layout)
        self.setWidget(container)

    def _init_connection(self):
        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._search.textChanged.connect(self._on_search_text_changed)

    def _init_selection_stream(self):
        self._selection_stream = StreamReader(
            stream=self._client.marker_stub.ListenSelectionChanges(empty_pb2.Empty()),
            on_data=self._handle_selection_change,
        )

    def _handle_selection_change(self, object_id_msg):
        QMetaObject.invokeMethod(
            self,
            "_select_object",
            Qt.QueuedConnection,
            Q_ARG(str, object_id_msg.id),
        )

    @Slot(str)
    def _select_object(self, object_id: str):
        source_index = self._model.findItem(object_id)
        if not source_index.isValid():
            return

        proxy_index = self._proxy_model.mapFromSource(source_index)
        if not proxy_index.isValid():
            return

        sel_model = self._view.selectionModel()
        sel_model.clearSelection()
        sel_model.select(
            proxy_index,
            QItemSelectionModel.Select | QItemSelectionModel.Rows,
        )
        self._view.scrollTo(proxy_index)

    def _search_filter(
        self,
        source_row: int,
        source_parent: QModelIndex,
        source_model: GRPCObjectsModel,
    ):
        search_text = self._search.text().strip().lower()
        if not search_text:
            return True

        for col in (
            GRPCObjectsModel.Columns.Name,
            GRPCObjectsModel.Columns.Path,
            GRPCObjectsModel.Columns.Type,
            GRPCObjectsModel.Columns.Id,
        ):
            index = source_model.index(source_row, col, source_parent)
            data = source_model.data(index, Qt.ItemDataRole.DisplayRole)
            if data and search_text in str(data).lower():
                return True

        parent_index = source_model.index(source_row, 0, source_parent)
        for i in range(source_model.rowCount(parent_index)):
            if self._search_filter(i, parent_index, source_model):
                return True

        return False

    def _on_search_text_changed(self):
        self._proxy_model.invalidateFilter()

    def _on_selection_changed(self):
        selected_indexes = self._view.selectionModel().selectedIndexes()
        selected_index = selected_indexes[0] if selected_indexes else QModelIndex()

        object_id = None
        if selected_index.isValid():
            source_index = self._proxy_model.mapToSource(selected_index)
            object_id = self._model.data(
                source_index.sibling(source_index.row(), GRPCObjectsModel.Columns.Id),
                Qt.ItemDataRole.DisplayRole,
            )

        self.current_object_changed.emit(object_id)
