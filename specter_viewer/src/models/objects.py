import json
import enum
import typing

from PySide6.QtCore import (
    Qt,
    Signal,
    QAbstractItemModel,
    QSortFilterProxyModel,
    QModelIndex,
    QMetaObject,
    Slot,
    QTimer,
    QThread,
    Q_ARG,
)
from google.protobuf import empty_pb2

from specter.proto.specter_pb2 import ObjectId, ObjectSearchQuery
from specter.client import Client, StreamReader


class ObjectNode:
    def __init__(
        self,
        id: typing.Optional[str] = None,
        parent: typing.Optional["ObjectNode"] = None,
    ):
        self.id = id
        self.name = None
        self.path = None
        self.type = None
        self.parent = parent
        self.children = []

    def __eq__(self, other):
        if isinstance(other, ObjectNode):
            return self.id == other.id
        elif isinstance(other, str):
            return self.id == other
        raise NotImplemented

    def child(self, row: int) -> typing.Optional["ObjectNode"]:
        return self.children[row] if 0 <= row < len(self.children) else None

    def row(self) -> int:
        return self.parent.children.index(self) if self.parent else 0

    @property
    def query(self) -> str:
        return getattr(self, "_query", None)

    @query.setter
    def query(self, query: typing.Optional[str]) -> str:
        self._query = query
        if self._query:
            parsed_query = json.loads(self._query)
            self.name = parsed_query["path"].split("/")[-1]
            self.path = parsed_query["path"]
            self.type = parsed_query["type"]


class ObjectsModel(QAbstractItemModel):
    class CustomDataRoles(enum.IntEnum):
        NodeRole = Qt.ItemDataRole.UserRole
        QueryRole = Qt.ItemDataRole.UserRole + 1

    class Columns(enum.IntEnum):
        Name = 0
        Path = 1
        Type = 2
        Id = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = ObjectNode()
        self._id_cache = {}

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            parent_node = parent.internalPointer()
            return len(parent_node.children)
        return len(self._root.children)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(ObjectsModel.Columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole) -> typing.Any:
        if not index.isValid():
            return None

        node = index.internalPointer()
        if role == Qt.ItemDataRole.DisplayRole:
            match index.column():
                case ObjectsModel.Columns.Name:
                    return node.name
                case ObjectsModel.Columns.Type:
                    return node.type
                case ObjectsModel.Columns.Path:
                    return node.path
                case ObjectsModel.Columns.Id:
                    return node.id
        elif role == ObjectsModel.CustomDataRoles.NodeRole:
            return node
        elif role == ObjectsModel.CustomDataRoles.QueryRole:
            return node.query

    def headerData(
        self, section, orientation, role=Qt.ItemDataRole.DisplayRole
    ) -> typing.Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            match section:
                case ObjectsModel.Columns.Name:
                    return "Name"
                case ObjectsModel.Columns.Type:
                    return "Type"
                case ObjectsModel.Columns.Path:
                    return "Path"
                case ObjectsModel.Columns.Id:
                    return "Id"

    def index(self, row, column, parent=QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_node = parent.internalPointer() if parent.isValid() else self._root
        child_node = (
            parent_node.children[row] if row < len(parent_node.children) else None
        )

        if child_node:
            return self.createIndex(row, column, child_node)

        return QModelIndex()

    def parent(self, index) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        child_node = index.internalPointer()
        parent_node = child_node.parent

        if parent_node is None or parent_node == self._root:
            return QModelIndex()

        return self.createIndex(parent_node.row(), 0, parent_node)

    def _update_cache(self, node: ObjectNode):
        self._id_cache[node.id] = node
        for child in node.children:
            self._update_cache(child)

    def _remove_from_cache(self, node: ObjectNode):
        if node.id in self._id_cache:
            del self._id_cache[node.id]
        for child in node.children:
            self._remove_from_cache(child)

    def findItem(
        self, object_id: str, parent=QModelIndex(), recursive: bool = True
    ) -> QModelIndex:
        node = self._id_cache.get(object_id)
        if not node:
            return QModelIndex()

        index = self.createIndex(node.row(), 0, node)
        if not recursive and self.parent(index) != parent:
            return QModelIndex()

        return index

    @Slot(str, QModelIndex)
    def createItem(self, object_id: str, parent_index=QModelIndex()) -> QModelIndex:
        parent_node = (
            parent_index.internalPointer() if parent_index.isValid() else self._root
        )
        new_node = ObjectNode(object_id, parent_node)
        row_count = self.rowCount(parent_index)

        self.beginInsertRows(parent_index, row_count, row_count)
        new_node.parent = parent_node
        parent_node.children.append(new_node)
        self._update_cache(new_node)
        self.endInsertRows()

        return self.createIndex(new_node.row(), 0, new_node)

    @Slot(str, QModelIndex)
    def addItem(self, node: ObjectNode, parent_index=QModelIndex()) -> QModelIndex:
        parent_node = (
            parent_index.internalPointer() if parent_index.isValid() else self._root
        )
        row_count = self.rowCount(parent_index)

        self.beginInsertRows(parent_index, row_count, row_count)
        node.parent = parent_node
        parent_node.children.append(node)
        self._update_cache(node)
        self.endInsertRows()

        return self.createIndex(node.row(), 0, node)

    @Slot(str, QModelIndex)
    def takeItem(self, object_id: str) -> typing.Optional[ObjectNode]:
        object_index = self.findItem(object_id)
        assert object_index.isValid()

        parent_index = object_index.parent()
        parent_node = (
            parent_index.internalPointer() if parent_index.isValid() else self._root
        )

        row_index = object_index.row()
        self.beginRemoveRows(parent_index, row_index, row_index)
        node = parent_node.children.pop(row_index)
        self._remove_from_cache(node)
        self.endRemoveRows()

        return node

    @Slot(str, QModelIndex)
    def updateItem(self, object_id: str, object_query: str):
        object_index = self.findItem(object_id)
        assert object_index.isValid()

        object_node = object_index.internalPointer()
        assert object_node

        if object_node.query != object_query:
            object_node.query = object_query

            self.dataChanged.emit(
                object_index.sibling(object_index.row(), ObjectsModel.Columns.Name),
                object_index.sibling(object_index.row(), ObjectsModel.Columns.Id),
                [Qt.ItemDataRole.DisplayRole],
            )

        return object_index


class GRPCObjectsModel(ObjectsModel):
    def __init__(self, client: Client, parent=None):
        super().__init__(parent)
        self._client = client

        self._stream_reader = StreamReader(
            stream=self._client.object_stub.ListenTreeChanges(empty_pb2.Empty()),
            on_data=self._handle_tree_changes,
        )

    def _handle_tree_changes(self, change):
        if change.HasField("added"):
            QMetaObject.invokeMethod(
                self,
                "_handle_object_added",
                Qt.QueuedConnection,
                Q_ARG(str, change.added.object_id.id),
                Q_ARG(str, change.added.parent_id.id),
            )
        elif change.HasField("removed"):
            QMetaObject.invokeMethod(
                self,
                "_handle_object_removed",
                Qt.QueuedConnection,
                Q_ARG(str, change.removed.object_id.id),
            )
        elif change.HasField("reparented"):
            QMetaObject.invokeMethod(
                self,
                "_handle_object_reparented",
                Qt.QueuedConnection,
                Q_ARG(str, change.reparented.object_id.id),
                Q_ARG(str, change.reparented.parent_id.id),
            )
        elif change.HasField("renamed"):
            QMetaObject.invokeMethod(
                self,
                "_handle_object_renamed",
                Qt.QueuedConnection,
                Q_ARG(str, change.renamed.object_id.id),
                Q_ARG(str, change.renamed.object_query.query),
            )

    @Slot(str, str)
    def _handle_object_added(self, object_id, parent_id):
        parent_index = self.findItem(parent_id)
        self.createItem(object_id, parent_index)

    @Slot(str)
    def _handle_object_removed(self, object_id):
        index = self.findItem(object_id)
        assert index.isValid()

        self.takeItem(object_id)

    @Slot(str, str)
    def _handle_object_reparented(self, object_id, parent_id):
        index = self.findItem(object_id)
        assert index.isValid()

        node = self.takeItem(object_id)

        new_parent_index = self.findItem(parent_id)
        self.addItem(node, new_parent_index)

    @Slot(str, str)
    def _handle_object_renamed(self, object_id: str, object_query: str):
        self.updateItem(object_id, object_query)
