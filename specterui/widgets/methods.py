import typing
import dataclasses
import datetime

from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTreeView,
    QMenu,
    QMessageBox,
    QHeaderView,
)
from PySide6.QtCore import Qt, SignalInstance, QModelIndex, QAbstractItemModel, QPoint

from specterui.client import Client
from specterui.delegates import MethodListDelegate
from specterui.models import (
    MethodListModel,
    DataclassTreeItem,
    HasNoDefaultError,
    GRPCMethodsModel,
)


class MethodsListTreeView(QTreeView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._expanded_items: typing.Set[typing.Tuple[str, ...]] = set()

        self.expanded.connect(lambda index: self._on_expansion_change(index, True))
        self.collapsed.connect(lambda index: self._on_expansion_change(index, False))

        self._model_signals: typing.List[SignalInstance] = []

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _get_item_path(self, index: QModelIndex) -> typing.Tuple[str, ...]:
        path = ()
        current = index
        while (
            current.isValid()
            and current.internalPointer() is not None
            and current.internalPointer().parent() is not None
        ):
            path = (current.internalPointer().name,) + path
            current = current.parent()
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
            if isinstance(model, MethodListModel):
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

        item = index.internalPointer()
        if isinstance(item, DataclassTreeItem) and item.field is not None:
            try:
                model = self.model()
                if isinstance(model, MethodListModel):
                    default_val = model.get_default_value(item.field)
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
        if isinstance(model, MethodListModel):
            try:
                model.setData(
                    index, None, MethodListModel.CustomDataRoles.DefaultValueRole
                )
            except Exception as exception:
                QMessageBox.warning(
                    self, "Error", f"Could not set to default: {exception}"
                )


class MethodsDock(QDockWidget):
    def __init__(self, client: Client):
        super().__init__("Methods")
        self._client = client
        self._init_ui()

    def _init_ui(self):
        self._model = GRPCMethodsModel(self._client)
        self._delegate = MethodListDelegate(self)
        self._view = MethodsListTreeView(self)
        self._view.setModel(self._model)
        self._view.setItemDelegate(self._delegate)
        self._view.header().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._view.setUniformRowHeights(True)
        self._view.setAlternatingRowColors(True)

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self._view)
        container.setLayout(layout)
        self.setWidget(container)

    def set_object(self, query: typing.Optional[str]):
        self._model.set_object(query)
