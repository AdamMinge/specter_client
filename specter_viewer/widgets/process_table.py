import enum
import psutil
import typing
import dataclasses

from PySide6.QtWidgets import QHeaderView, QTableView
from PySide6.QtCore import (
    Signal,
    Slot,
    QSortFilterProxyModel,
    Qt,
    QModelIndex,
    Property,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem


@dataclasses.dataclass
class Process:
    name: str
    pid: int
    username: str


class ProcessTable(QTableView):
    class Columns(enum.IntEnum):
        Name = 0
        PID = 1
        User = 2

    class SortFilterProxyModel(QSortFilterProxyModel):
        def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
            column = left.column()

            if column == ProcessTable.Columns.PID:
                left_value = int(left.data())
                right_value = int(right.data())
                return left_value < right_value
            else:
                return super().lessThan(left, right)

    current_changed = Signal()

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        self._model = QStandardItemModel(0, 3, self)
        self._model.setHorizontalHeaderLabels(["Process", "ID", "User"])

        self._proxy_model = ProcessTable.SortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(0)

        self.setModel(self._proxy_model)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.setSortingEnabled(True)
        self.sortByColumn(ProcessTable.Columns.Name, Qt.SortOrder.AscendingOrder)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionsClickable(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        self.selectionModel().selectionChanged.connect(self._handle_current_changed)

    def filter(self, filter):
        self._proxy_model.setFilterWildcard(filter)

    def refresh(self):
        self._model.removeRows(0, self._model.rowCount())

        for proc in psutil.process_iter(["pid", "name", "username"]):
            try:
                name = proc.info["name"]
                pid = proc.info["pid"]
                username = proc.info["username"]
                self._append_process(Process(name=name, pid=pid, username=username))

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    def _current(self) -> typing.Optional[Process]:
        indexes = self.selectionModel().selectedIndexes()
        if len(indexes) == 0:
            return None

        index = indexes[0]
        name = str(self._model.item(index.row(), ProcessTable.Columns.Name).text())
        id = int(self._model.item(index.row(), ProcessTable.Columns.PID).text())
        username = str(self._model.item(index.row(), ProcessTable.Columns.User).text())

        return Process(name=name, pid=id, username=username)

    current = Property("QVariant", _current, notify=current_changed)  # type: ignore

    def _append_process(self, process: Process):
        name = QStandardItem(process.name)
        pid = QStandardItem(str(process.pid))
        username = QStandardItem(process.username)

        name.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        pid.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        username.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

        self._model.appendRow([name, pid, username])

    @Slot()
    def _handle_current_changed(self):
        self.current_changed.emit()
