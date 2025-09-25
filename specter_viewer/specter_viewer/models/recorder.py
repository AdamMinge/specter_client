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


EVENT_FORMATTERS = {
    "context_menu_opened": lambda ev: f"ContextMenuOpened {ev.object_query.query}",
    "button_clicked": lambda ev: f"ButtonClicked {ev.object_query.query}",
    "button_toggled": lambda ev: f"ButtonToggled {ev.object_query.query} checked={ev.checked}",
    "combo_box_current_changed": lambda ev: f"ComboBoxCurrentChanged {ev.object_query.query} index={ev.index}",
    "spin_box_value_changed": lambda ev: f"SpinBoxValueChanged {ev.object_query.query} value={ev.value}",
    "double_spin_box_value_changed": lambda ev: f"DoubleSpinBoxValueChanged {ev.object_query.query} value={ev.value}",
    "slider_value_changed": lambda ev: f"SliderValueChanged {ev.object_query.query} value={ev.value}",
    "tab_current_changed": lambda ev: f"TabCurrentChanged {ev.object_query.query} index={ev.index}",
    "tab_closed": lambda ev: f"TabClosed {ev.object_query.query} index={ev.index}",
    "tab_moved": lambda ev: f"TabMoved {ev.object_query.query} from={ev.from_} to={ev.to}",
    "tool_box_current_changed": lambda ev: f"ToolBoxCurrentChanged {ev.object_query.query} index={ev.index}",
    "action_triggered": lambda ev: f"ActionTriggered {ev.object_query.query}",
    "text_edit_text_changed": lambda ev: f"TextEditTextChanged {ev.object_query.query} value={ev.value}",
    "line_edit_text_changed": lambda ev: f"LineEditTextChanged {ev.object_query.query} value={ev.value}",
    "line_edit_return_pressed": lambda ev: f"LineEditReturnPressed {ev.object_query.query}",
}


class GRPCRecorderConsoleItem(BaseConsoleItem):
    def __init__(self, id: str, client: Client, parent=None):
        super().__init__(parent)
        self._id = id
        self._lines: list[str] = []
        self._events: list[typing.Any] = []
        self._client = client
        self._stream_reader = None

    def get_current_line_list(self) -> typing.Tuple[list[str], int]:
        return self._lines, 0

    def get_events(self) -> list[typing.Any]:
        return self._events

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
        which = action.WhichOneof("event")
        assert which

        ev = getattr(action, which)
        formatter = EVENT_FORMATTERS.get(which, lambda ev: f"Unknown event: {which}")
        text = formatter(ev)

        self._events.append(action)
        self._lines.append(text)

        self.loadedLinesChanged.emit([text], len(self._lines))


class ConsoleModel(QAbstractItemModel):
    ConsoleItemRole = Qt.UserRole + 1
    RecordedEventsRole = Qt.UserRole + 2

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
        elif role == ConsoleModel.ConsoleItemRole:
            return item
        elif role == ConsoleModel.ConsoleItemRole:
            if isinstance(item, GRPCRecorderConsoleItem):
                return item.get_events()
            return []
        else:
            return None
