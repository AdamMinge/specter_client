import typing

from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTreeView,
    QMenu,
    QHeaderView,
    QLineEdit,
)
from PySide6.QtCore import Qt, SignalInstance, QModelIndex, QAbstractItemModel, QPoint

from specter.client import Client

from specter_viewer.delegates.methods import MethodButtonDelegate
from specter_viewer.models.proxies import MultiColumnSortFilterProxyModel
from specter_viewer.models.methods import (
    MethodsModel,
    PropertiesTreeItem,
    HasNoDefaultError,
    GRPCMethodsModel,
)


class MethodsTreeView(QTreeView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._expanded_items: typing.Set[typing.Tuple[str, ...]] = set()

        self.expanded.connect(lambda index: self._on_expansion_change(index, True))
        self.collapsed.connect(lambda index: self._on_expansion_change(index, False))

        self._model_signals: typing.List[SignalInstance] = []

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.setItemDelegateForColumn(1, MethodButtonDelegate(self))

    def _get_item_path(self, index: QModelIndex) -> typing.Tuple[str, ...]:
        model = self.model()

        path = ()
        current_index = index
        current_item = model.data(
            current_index, MethodsModel.CustomDataRoles.TreeItemRole
        )

        while current_item is not None and current_item.parent() is not None:
            path = (current_item.name,) + path
            current_index = current_index.parent()
            current_item = model.data(
                current_index, MethodsModel.CustomDataRoles.TreeItemRole
            )
        return path

    def _on_expansion_change(self, index: QModelIndex, expanded: bool) -> None:
        item_path = self._get_item_path(index)
        if not item_path:
            return

        if expanded:
            self._expanded_items.add(item_path)
        else:
            self._expanded_items.discard(item_path)

    def _apply_expansion_state_recursive(self, index: QModelIndex) -> None:
        if not index.isValid():
            return

        item_path = self._get_item_path(index)
        if item_path in self._expanded_items:
            self.expand(index)
        else:
            self.collapse(index)

        model = self.model()
        if model:
            for row in range(model.rowCount(index)):
                child_index = model.index(row, 0, index)
                self._apply_expansion_state_recursive(child_index)

    def setModel(self, model: QAbstractItemModel | None) -> None:
        for signal_connection in self._model_signals:
            try:
                pass
            except TypeError:
                pass
        self._model_signals.clear()

        super().setModel(model)

        if model is not None:
            self._model_signals.append(
                model.modelReset.connect(self._restore_expansion_state)
            )
            self._restore_expansion_state()

    def _restore_expansion_state(self) -> None:
        self.blockSignals(True)
        model = self.model()
        if model:
            root_index = self.rootIndex()
            for row in range(model.rowCount(root_index)):
                top_level_index = model.index(row, 0, root_index)
                self._apply_expansion_state_recursive(top_level_index)
        self.blockSignals(False)

    def _show_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        index = self.indexAt(pos)

        if not index.isValid():
            return

        model = self.model()
        item = model.data(index, MethodsModel.CustomDataRoles.TreeItemRole)
        if isinstance(item, PropertiesTreeItem) and item.field is not None:
            try:
                model = self.model()
                if isinstance(model, MethodsModel):
                    default_val = model.data(
                        index, MethodsModel.CustomDataRoles.DefaultValueRole
                    )
                    current_val = model.data(index, Qt.ItemDataRole.EditRole)

                    if default_val != current_val:
                        action = menu.addAction(f"Set to default ({default_val})")
                        action.triggered.connect(
                            lambda: self._set_index_to_default(index)
                        )
                    else:
                        action = menu.addAction("Set to default (unchanged)")
                        action.setEnabled(False)
            except HasNoDefaultError:
                action = menu.addAction("Set to default (no default available)")
                action.setEnabled(False)
            except Exception as e:
                action = menu.addAction("Set to default (error)")
                action.setEnabled(False)

        if menu.actions():
            menu.exec(self.mapToGlobal(pos))

    def _set_index_to_default(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        model = self.model()
        model.setData(index, None, MethodsModel.CustomDataRoles.DefaultValueRole)


class MethodsDock(QDockWidget):
    def __init__(self, client: Client):
        super().__init__("Methods")
        self._client = client
        self._init_ui()
        self._init_connection()

    def _init_ui(self):
        self._model = GRPCMethodsModel(self._client)

        self._proxy_model = MultiColumnSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.sort_by_columns(
            [0],
            [Qt.SortOrder.DescendingOrder],
        )
        self._proxy_model.set_filter_function("search_filter", self._search_filter)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search methods...")

        self._view = MethodsTreeView()
        self._view.setModel(self._proxy_model)
        self._view.header().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._view.setUniformRowHeights(True)
        self._view.setAlternatingRowColors(True)

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
        source_model: GRPCMethodsModel,
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
        self, index: QModelIndex, model: GRPCMethodsModel, search_text: str
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
