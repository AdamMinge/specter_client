import json
import enum
import typing

from PySide6.QtCore import (
    Qt,
    QAbstractItemModel,
    QModelIndex,
    QMetaObject,
    Slot,
    Q_ARG,
)
from google.protobuf import empty_pb2
from specterui.proto.specter_pb2 import OptionalObject

from specterui.client import Client, StreamReader


class ObjectNode:
    def __init__(
        self,
        query: typing.Optional[str] = None,
        parent: typing.Optional["ObjectNode"] = None,
    ):
        self.query = query
        self.parent = parent
        self.children = []

    def __eq__(self, other):
        if isinstance(other, ObjectNode):
            return self.query == other.query
        elif isinstance(other, str):
            return self.query == other
        raise NotImplemented

    def child(self, row: int) -> typing.Optional["ObjectNode"]:
        return self.children[row] if 0 <= row < len(self.children) else None

    def row(self) -> int:
        return self.parent.children.index(self) if self.parent else 0

    @property
    def query(self) -> str:
        return self._query

    @query.setter
    def query(self, query: typing.Optional[str]) -> str:
        self._query = query
        if query:
            parsed_query = json.loads(query)
            self.name = parsed_query["path"].split("/")[-1]
            self.path = parsed_query["path"]
            self.type = parsed_query["type"]


class ObjectsModel(QAbstractItemModel):
    class Columns(enum.IntEnum):
        Name = 0
        Path = 1
        Type = 2
        Query = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = ObjectNode()
        self._query_cache = {}

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
        elif role == Qt.ItemDataRole.UserRole:
            match index.column():
                case ObjectsModel.Columns.Query:
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
        self._query_cache[node.query] = node
        for child in node.children:
            self._update_cache(child)

    def _remove_from_cache(self, node: ObjectNode):
        if node.query in self._query_cache:
            del self._query_cache[node.query]
        for child in node.children:
            self._remove_from_cache(child)

    def findItem(
        self, query: str, parent=QModelIndex(), recursive: bool = True
    ) -> QModelIndex:
        node = self._query_cache.get(query)
        if not node:
            return QModelIndex()

        index = self.createIndex(node.row(), 0, node)
        if not recursive and self.parent(index) != parent:
            return QModelIndex()

        return index

    @Slot(str, QModelIndex)
    def createItem(self, query: str, parent_index=QModelIndex()) -> QModelIndex:
        parent_node = (
            parent_index.internalPointer() if parent_index.isValid() else self._root
        )
        new_node = ObjectNode(query, parent_node)
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
    def takeItem(
        self, query: str, parent_index=QModelIndex()
    ) -> typing.Optional[ObjectNode]:
        parent_node = (
            parent_index.internalPointer() if parent_index.isValid() else self._root
        )
        find_index = self.findItem(query, parent_index, recursive=False)

        if not find_index.isValid():
            return None

        row_index = find_index.row()
        self.beginRemoveRows(parent_index, row_index, row_index)
        node = parent_node.children.pop(row_index)
        self._remove_from_cache(node)
        self.endRemoveRows()

        return node

    @Slot(str, QModelIndex)
    def updateItem(
        self, old_query: str, new_query: str, parent_index=QModelIndex()
    ) -> QModelIndex:
        node = self._query_cache.get(old_query)
        if not node:
            return QModelIndex()

        if old_query in self._query_cache:
            del self._query_cache[old_query]
        node.query = new_query
        self._query_cache[new_query] = node

        index = self.createIndex(node.row(), 0, node)
        self.dataChanged.emit(
            index.sibling(index.row(), ObjectsModel.Columns.Name),
            index.sibling(index.row(), ObjectsModel.Columns.Path),
            [Qt.ItemDataRole.DisplayRole],
        )
        return index


class GRPCObjectsModel(ObjectsModel):
    def __init__(self, client: Client, parent=None):
        super().__init__(parent)
        self._client = client

        self._stream_reader = StreamReader(
            stream=self._client.object_stub.ListenTreeChanges(empty_pb2.Empty()),
            on_data=self.handle_tree_changes,
        )
        self.fetch_initial_state()

    def fetch_initial_state(self):
        response = self._client.object_stub.GetTree(OptionalObject())
        self.build_tree(response.nodes)

    def build_tree(self, object_nodes, parent_index=QModelIndex()):
        for object_node in object_nodes:
            node_index = self.createItem(object_node.object.query, parent_index)
            self.build_tree(object_node.nodes, node_index)

    def handle_tree_changes(self, change):
        if change.HasField("added"):
            QMetaObject.invokeMethod(
                self,
                "handle_object_added",
                Qt.QueuedConnection,
                Q_ARG(str, change.added.object.query),
                Q_ARG(str, change.added.parent.query),
            )
        elif change.HasField("removed"):
            QMetaObject.invokeMethod(
                self,
                "handle_object_removed",
                Qt.QueuedConnection,
                Q_ARG(str, change.removed.object.query),
            )
        elif change.HasField("reparented"):
            QMetaObject.invokeMethod(
                self,
                "handle_object_reparented",
                Qt.QueuedConnection,
                Q_ARG(str, change.reparented.object.query),
                Q_ARG(str, change.reparented.parent.query),
            )
        elif change.HasField("renamed"):
            QMetaObject.invokeMethod(
                self,
                "handle_object_renamed",
                Qt.QueuedConnection,
                Q_ARG(str, change.renamed.old_object.query),
                Q_ARG(str, change.renamed.new_object.query),
            )

    @Slot(str, str)
    def handle_object_added(self, object, parent):
        parent_index = self.findItem(parent)
        self.createItem(object, parent_index)

    @Slot(str)
    def handle_object_removed(self, object):
        index = self.findItem(object)
        if not index.isValid():
            return

        parent_index = self.parent(index)
        self.takeItem(object, parent_index)

    @Slot(str, str)
    def handle_object_reparented(self, object, parent):
        index = self.findItem(object)
        if not index.isValid():
            return

        old_parent_index = self.parent(index)
        node = self.takeItem(object, old_parent_index)

        new_parent_index = self.findItem(parent)
        self.addItem(node, new_parent_index)

    @Slot(str, str)
    def handle_object_renamed(self, old_object, new_object):
        index = self.findItem(old_object)
        if not index.isValid():
            return

        parent_index = self.parent(index)
        self.updateItem(old_object, new_object, parent_index)
