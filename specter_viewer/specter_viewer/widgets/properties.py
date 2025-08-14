import typing

from PySide6.QtCore import Qt, SignalInstance, QModelIndex, QAbstractItemModel, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTableView,
    QHeaderView,
    QTreeView,
    QLineEdit,
    QMenu,
)

from specter.client import Client

from specter_viewer.models.proxies import MultiColumnSortFilterProxyModel
from specter_viewer.models.properties import (
    GRPCPropertiesModel,
    HasNoDefaultError,
    PropertiesTreeItem,
)


class PropertiesView(QTreeView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._expanded_items = set({})
        self.expanded.connect(
            lambda index, expanded=True: self._on_expansion_change(index, expanded)
        )
        self.collapsed.connect(
            lambda index, expanded=False: self._on_expansion_change(index, expanded)
        )

        self._model_signals: typing.List[SignalInstance] = []

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.reset_expansion_state)

    def _on_expansion_change(self, index: QModelIndex, expanded: bool) -> None:
        attr_name = index.data(GRPCPropertiesModel.CustomDataRoles.AttributeNameRole)
        if expanded and attr_name not in self._expanded_items:
            self._expanded_items.add(attr_name)
        elif not expanded and attr_name in self._expanded_items:
            self._expanded_items.remove(attr_name)

    def _get_set_expansion_state(self, index: QModelIndex) -> None:
        if index is None or not index.isValid():
            return

        tree_item: PropertiesTreeItem = index.data(
            GRPCPropertiesModel.CustomDataRoles.TreeItemRole
        )
        if tree_item.name in self._expanded_items:
            self.expand(index)
        else:
            self.collapse(index)

        for child_nr in range(tree_item.child_count()):
            child = tree_item.child(child_nr)
            child_index = self.model().index(child.row(), 0, index)
            self._get_set_expansion_state(child_index)

    def reset_expansion_state(self) -> None:
        self.blockSignals(True)
        root = self.rootIndex()
        for child_nr in range(self.model().rowCount(root)):
            index = self.model().index(child_nr, 0, root)
            self._get_set_expansion_state(index)
        self.blockSignals(False)

    def setModel(self, model: QAbstractItemModel | None) -> None:
        super().setModel(model)
        if len(self._model_signals) > 0:
            for signal in self._model_signals:
                self.disconnect(signal)
            self._model_signals = []

        if model is not None:
            self._model_signals.append(
                model.modelReset.connect(self.reset_expansion_state)
            )

    def mousePressEvent(self, event: QMouseEvent) -> bool:
        if not event.button() == Qt.MouseButton.RightButton:
            return super().mousePressEvent(event)
        pos = event.pos()
        index = self.indexAt(pos)
        if not index.isValid():
            return super().mousePressEvent(event)
        return self._try_context_menu_event(pos)

    def _try_context_menu_event(self, pos: QPoint) -> bool:
        menu = QMenu(self)
        index = self.indexAt(pos)
        if not index.isValid():
            return False

        cur_data = index.data(Qt.ItemDataRole.EditRole)
        try:
            default_val = index.data(
                GRPCPropertiesModel.CustomDataRoles.DefaultValueRole
            )
            if default_val != cur_data:
                menu.addAction(
                    f"Set to default ({default_val})",
                    lambda x=index: self.set_index_to_default(index),
                )
            else:
                menu.addAction("Set to default (unchanged)", None)
        except HasNoDefaultError:
            menu.addAction("Set to default (unchanged)", None)

        menu.exec(self.mapToGlobal(pos))
        return True

    def set_index_to_default(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        model = self.model()
        model.setData(index, None, GRPCPropertiesModel.CustomDataRoles.DefaultValueRole)


class PropertiesDock(QDockWidget):
    def __init__(self, client: Client):
        super().__init__("Properties")
        self._client = client
        self._init_ui()
        self._init_connection()

    def _init_ui(self):
        self._model = GRPCPropertiesModel(self._client)
        self._proxy_model = MultiColumnSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.sort_by_columns(
            [0],
            [Qt.SortOrder.DescendingOrder],
        )
        self._proxy_model.set_filter_function("search_filter", self._search_filter)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search properties...")

        self._view = PropertiesView()
        self._view.setModel(self._proxy_model)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setAlternatingRowColors(True)
        self._view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._view.header().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self._search)
        layout.addWidget(self._view)
        container.setLayout(layout)
        self.setWidget(container)

    def _init_connection(self):
        self._search.textChanged.connect(self._on_search_text_changed)

    def _search_filter(
        self,
        source_row: int,
        source_parent: QModelIndex,
        source_model: GRPCPropertiesModel,
    ):
        search_text = self._search.text().strip().lower()

        index = source_model.index(source_row, 0, source_parent)
        data = source_model.data(index, Qt.ItemDataRole.DisplayRole)

        if isinstance(data, str) and data.endswith("type"):
            return False

        if not search_text:
            return True

        root_index = index
        while root_index.parent().isValid():
            root_index = root_index.parent()

        if self._subtree_matches(root_index, source_model, search_text):
            return True

        return False

    def _subtree_matches(
        self, index: QModelIndex, model: GRPCPropertiesModel, search_text: str
    ) -> bool:
        data = model.data(index, Qt.ItemDataRole.DisplayRole)
        if data and search_text in str(data).lower():
            return True

        for i in range(model.rowCount(index)):
            if self._subtree_matches(model.index(i, 0, index), model, search_text):
                return True

        return False

    def _on_search_text_changed(self):
        self._proxy_model.invalidateFilter()

    def set_object(self, object_id: str):
        self._proxy_model.setSourceModel(None)
        self._model.set_object(object_id)
        self._proxy_model.setSourceModel(self._model)
