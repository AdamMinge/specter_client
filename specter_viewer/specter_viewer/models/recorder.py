import typing
import abc

from PySide6.QtCore import Qt, QObject, Signal, QAbstractItemModel, QModelIndex
from PySide6.QtWidgets import QStyle, QApplication

from google.protobuf import empty_pb2

from specter.client import Client, StreamReader


class BaseConsoleItem(QObject):
    loadedLinesChanged = Signal(list, int)
    dataChanged = Signal()

    @abc.abstractmethod
    def data(self, role: Qt.ItemDataRole, column: int = 0):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_current_line_list(self) -> typing.Tuple[list[str], int]:
        raise NotImplementedError()


class GRPCRecorderConsoleItem(BaseConsoleItem):
    def __init__(self, id: str, client: Client, parent=None):
        super().__init__(parent)
        self._id = id
        self._lines = []
        self._client = client
        self._stream_reader = None

    def get_current_line_list(self) -> typing.Tuple[list[str], int]:
        return self._lines, 0

    def data(self, role: Qt.ItemDataRole, column: int = 0) -> typing.Any:
        if role == Qt.ItemDataRole.DisplayRole:
            return self._id
        else:
            return None

    def start(self):
        if not self._stream_reader:
            self._stream_reader = StreamReader(
                stream=self._client.recorder_stub.ListenCommands(empty_pb2.Empty()),
                on_data=self.handle_recorded_action,
            )

    def stop(self):
        if self._stream_reader:
            self._stream_reader.stop()
            self._stream_reader = None

    def is_running(self) -> bool:
        return self._stream_reader is not None

    def handle_recorded_action(self, action):
        commands = [action.command]
        self._lines.extend(commands)
        self.loadedLinesChanged.emit(commands, len(self._lines))


class ConsoleModel(QAbstractItemModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._console_pixmap = QStyle.StandardPixmap.SP_TitleBarMaxButton
        self._console_icon = QApplication.style().standardIcon(self._console_pixmap)
        self._item_list = []

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 3

    def removeRow(self, row: int, parent: QModelIndex) -> bool:
        self.beginRemoveRows(parent, row, row)
        del self._item_list[row]
        self.endRemoveRows()
        self.modelReset.emit()
        return True

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not parent.isValid():
            return len(self._item_list)
        else:
            return 0

    def parent(self, index: QModelIndex) -> QModelIndex:
        return QModelIndex()

    def index(
        self, row: int, column: int, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        if not parent.isValid():
            return self.createIndex(row, column, self._item_list[row])
        else:
            return QModelIndex()

    def append_row(self, item: BaseConsoleItem):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self._item_list.append(item)
        item.dataChanged.connect(
            lambda *_: self.dataChanged.emit(
                self.index(self.rowCount() - 1, 0), self.index(self.rowCount() - 1, 2)
            )
        )

        self.endInsertRows()

    def add_item(self, item: BaseConsoleItem):
        self.append_row(item)

    def data(
        self, index: QModelIndex, role: Qt.ItemDataRole = Qt.ItemDataRole.DisplayRole
    ):
        if not index.isValid():
            return None

        item = index.internalPointer()

        assert isinstance(item, BaseConsoleItem)

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return item.data(role=role, column=index.column())
        elif role == Qt.ItemDataRole.DecorationRole:
            return self._console_icon
        elif role == Qt.ItemDataRole.UserRole + 1:
            return item
        else:
            return None
