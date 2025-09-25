import typing
import os

from PySide6.QtWidgets import (
    QSizePolicy,
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QToolButton,
    QHBoxLayout,
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QSplitter,
    QPlainTextEdit,
    QTableView,
    QFileDialog,
)
from PySide6.QtGui import QIcon, QPixmap, QTextCursor
from PySide6.QtCore import (
    Qt,
    QItemSelection,
    QModelIndex,
    QAbstractTableModel,
    QAbstractItemModel,
    Property,
    QMetaObject,
    QCoreApplication,
)

from specter.client import Client
from specter.scripts.generator import CodeGenerator

from specter_viewer.delegates.recorder import RecorderWidgetDelegate
from specter_viewer.models.proxies import MultiColumnSortFilterProxyModel
from specter_viewer.models.recorder import (
    GRPCRecorderConsoleItem,
    ConsoleModel,
    BaseConsoleItem,
)


class Ui_ConsoleWidget(object):
    def setupUi(self, ConsoleWidget):
        if not ConsoleWidget.objectName():
            ConsoleWidget.setObjectName("ConsoleWidget")
        ConsoleWidget.resize(1466, 346)
        self.verticalLayout = QVBoxLayout(ConsoleWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(ConsoleWidget)
        self.splitter.setObjectName("splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.splitter.setHandleWidth(5)
        self.consoleTextEdit = QPlainTextEdit(self.splitter)
        self.consoleTextEdit.setObjectName("consoleTextEdit")
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.consoleTextEdit.sizePolicy().hasHeightForWidth()
        )
        self.consoleTextEdit.setSizePolicy(sizePolicy)
        self.consoleTextEdit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.consoleTextEdit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.splitter.addWidget(self.consoleTextEdit)
        self.fileSelectionTableView = QTableView(self.splitter)
        self.fileSelectionTableView.setObjectName("fileSelectionTableView")
        self.splitter.addWidget(self.fileSelectionTableView)

        self.verticalLayout.addWidget(self.splitter)

        self.retranslateUi(ConsoleWidget)

        QMetaObject.connectSlotsByName(ConsoleWidget)

    def retranslateUi(self, ConsoleWidget):
        ConsoleWidget.setWindowTitle(
            QCoreApplication.translate("ConsoleWidget", "Form", None)
        )
        self.consoleTextEdit.setPlainText("")


class ConsoleWidget(QWidget):
    def __init__(
        self,
        parent: typing.Optional[QWidget] = None,
        display_max_blocks=1000,
        ui_text_min_update_interval: float = 0.05,
    ) -> None:
        super().__init__(parent)
        self._ui = Ui_ConsoleWidget()
        self._ui.setupUi(self)

        self._display_max_blocks = display_max_blocks
        self._ui.consoleTextEdit.setMaximumBlockCount(display_max_blocks)
        self._files_proxy_model = MultiColumnSortFilterProxyModel(self)
        self._ui.fileSelectionTableView.setModel(self._files_proxy_model)

        self._ui.fileSelectionTableView.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self._files_proxy_model.sort_by_columns(
            [1, 0],
            [Qt.SortOrder.DescendingOrder, Qt.SortOrder.AscendingOrder],
        )

        self._ui.fileSelectionTableView.hideColumn(1)
        self._ui.fileSelectionTableView.hideColumn(2)

        self._ui.fileSelectionTableView.verticalHeader().hide()
        self._ui.fileSelectionTableView.horizontalHeader().hide()

        self._ui.fileSelectionTableView.setFrameShape(QFrame.Shape.NoFrame)
        self._ui.fileSelectionTableView.setShowGrid(False)

        self._ui.fileSelectionTableView.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.set_console_width_percentage(50)

        self._ui.consoleTextEdit.setReadOnly(True)

        self._ui.fileSelectionTableView.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._ui.fileSelectionTableView.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._ui.fileSelectionTableView.mouseReleaseEvent = self.mouseReleaseEvent

        self.file_selection_delegate = RecorderWidgetDelegate(
            self._ui.fileSelectionTableView
        )
        self._ui.fileSelectionTableView.setItemDelegateForColumn(
            0, self.file_selection_delegate
        )
        self.file_selection_delegate.deleteHoverItem.connect(
            self.delete_file_selector_at_index
        )

        self._current_linechange_connect = None
        self._ui.fileSelectionTableView.viewport().setMouseTracking(True)

        self._ui.fileSelectionTableView.selectionModel().selectionChanged.connect(
            self.selection_changed
        )
        self._ui_text_min_update_interval = ui_text_min_update_interval

        self.currently_loaded_lines = [0, 0]

    def selection_changed(self, selection: QItemSelection):
        if self._current_linechange_connect is not None:
            self.disconnect(self._current_linechange_connect)
            self._current_linechange_connect = None

        if len(selection.indexes()) == 0:
            self._ui.consoleTextEdit.setPlainText("")
            return
        elif selection.indexes()[0].isValid():
            self._ui.consoleTextEdit.setPlainText("")
            index = selection.indexes()[0]
            item = self._files_proxy_model.data(
                index, role=Qt.ItemDataRole.UserRole + 1
            )
            assert isinstance(
                item, BaseConsoleItem
            ), "Item is not of type BaseConsoleItem"

            self._current_linechange_connect = item.loadedLinesChanged.connect(
                self.process_line_change
            )

            cur_line_list, from_index = item.get_current_line_list()
            self.process_line_change(cur_line_list, from_index)

            self._ui.consoleTextEdit.verticalScrollBar().setValue(
                self._ui.consoleTextEdit.verticalScrollBar().maximum()
            )

    @staticmethod
    def _get_index_nth_occurence(string: str, char: str, occurence: int) -> int:
        counter = 0
        if occurence <= 0:
            return 0
        for i, char in enumerate(string):
            if char == "\n":
                counter += 1
            if counter >= occurence:
                return i

        return -1

    def process_line_change(self, new_line_list: list[str], from_line: int = 0):
        if len(new_line_list) > self._display_max_blocks:
            from_line = from_line + len(new_line_list) - self._display_max_blocks
            new_line_list = new_line_list[-self._display_max_blocks :]

        new_loaded_lines = [
            min(self.currently_loaded_lines[0], from_line),
            max(from_line + len(new_line_list), self.currently_loaded_lines[1]),
        ]
        shift = 0

        if new_loaded_lines[1] - new_loaded_lines[0] > self._display_max_blocks:
            shift = new_loaded_lines[1] - self._display_max_blocks - new_loaded_lines[0]
            new_loaded_lines = (
                new_loaded_lines[1] - self._display_max_blocks,
                new_loaded_lines[1],
            )

        start_line = max(from_line - self.currently_loaded_lines[0], 0)

        at_end_scrollbar = (
            self._ui.consoleTextEdit.verticalScrollBar().value()
            > self._ui.consoleTextEdit.verticalScrollBar().maximum() - 4
        )

        cur_cursor = self._ui.consoleTextEdit.textCursor()
        cur_cursor.movePosition(QTextCursor.MoveOperation.Start)
        cur_cursor.movePosition(
            QTextCursor.MoveOperation.Down,
            QTextCursor.MoveMode.MoveAnchor,
            start_line,
        )

        cur_cursor.insertText("".join([i + "\n" for i in new_line_list]))

        if at_end_scrollbar:
            self._ui.consoleTextEdit.verticalScrollBar().setValue(
                self._ui.consoleTextEdit.verticalScrollBar().maximum() - 1
            )
        else:
            self._ui.consoleTextEdit.verticalScrollBar().setValue(
                self._ui.consoleTextEdit.verticalScrollBar().value() - shift
            )

        self.currently_loaded_lines = new_loaded_lines

    def dragMoveEvent(self, event) -> bool:
        event.setAccepted(True)
        return True

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            event.setAccepted(True)
            return
        return super().mouseReleaseEvent(event)

    def delete_file_selector_at_index(self, index: QModelIndex):
        original_index = self._files_proxy_model.mapToSource(index)

        selected_indexes = (
            self._ui.fileSelectionTableView.selectionModel().selectedIndexes()
        )
        self._files_proxy_model.sourceModel().removeRow(
            original_index.row(), original_index.parent()
        )

        selected_row = selected_indexes[0].row() if len(selected_indexes) > 0 else -1
        deleted_row = index.row()
        new_selected_row = selected_row

        if selected_row == deleted_row:
            if deleted_row < self._files_proxy_model.rowCount():
                new_selected_row = deleted_row
            elif (
                deleted_row - 1 >= 0
                and deleted_row - 1 < self._files_proxy_model.rowCount()
            ):
                new_selected_row = deleted_row - 1
            else:
                new_selected_row = -1
        elif selected_row > 0:
            if deleted_row < selected_row:
                new_selected_row = selected_row - 1
            else:
                new_selected_row = selected_row
        if new_selected_row >= 0:
            self._ui.fileSelectionTableView.setCurrentIndex(
                self._files_proxy_model.index(new_selected_row, 0)
            )
        else:
            self._ui.fileSelectionTableView.selectionModel().clearSelection()
            self.selection_changed(
                self._ui.fileSelectionTableView.selectionModel().selection()
            )

    @staticmethod
    def get_file_name_path_dict_in_edit_order(
        path: str, only_extensions: list | None = None
    ):
        filelist = sorted(
            os.listdir(path),
            key=lambda x: os.path.getmtime(os.path.join(path, x)),
            reverse=True,
        )

        for filename in filelist:
            if only_extensions is not None:
                if os.path.splitext(filename)[1] not in only_extensions:
                    filelist.remove(filename)

        return {
            os.path.splitext(filename)[0]: os.path.join(path, filename)
            for filename in filelist
        }

    def set_model(self, model: QAbstractTableModel | QAbstractItemModel):
        self._files_proxy_model.setSourceModel(model)
        self._ui.fileSelectionTableView.hideColumn(1)
        self._ui.fileSelectionTableView.hideColumn(2)

    def get_console_width_percentage(self) -> int:
        if self._ui.splitter.sizes()[0] == 0:
            return 0
        elif self._ui.splitter.sizes()[1] == 0:
            return 100

        return int(
            self._ui.splitter.sizes()[0]
            / (self._ui.splitter.sizes()[1] + self._ui.splitter.sizes()[0])
            * 100
        )

    def set_console_width_percentage(self, percentage: int) -> None:
        percentage = max(1, min(100, percentage))
        self._ui.splitter.setSizes([10 * percentage, 10 * (100 - percentage)])
        self._ui.splitter.setStretchFactor(0, percentage)
        self._ui.splitter.setStretchFactor(1, 100 - percentage)

    ConsoleWidthPercentage = Property(
        int, get_console_width_percentage, set_console_width_percentage
    )


class RecorderDock(QDockWidget):
    def __init__(self, client: Client):
        super().__init__("Recorder")
        self._client = client
        self._init_ui()
        self._init_connection()
        self._update_buttons()

    def _init_ui(self):
        self._model = ConsoleModel()
        self._view = ConsoleWidget(
            ui_text_min_update_interval=0.1, display_max_blocks=5000
        )
        self._view.set_model(self._model)
        self._view.set_console_width_percentage(80)

        self._new_button = self._make_tool_button("New", ":/icons/start.png")
        self._resume_button = self._make_tool_button("Resume", ":/icons/resume.png")
        self._pause_button = self._make_tool_button("Pause", ":/icons/pause.png")
        self._stop_button = self._make_tool_button("Stop", ":/icons/stop.png")
        self._export_button = self._make_tool_button("Export", ":/icons/export.png")

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        toolbar_layout.addWidget(self._new_button)
        toolbar_layout.addWidget(self._resume_button)
        toolbar_layout.addWidget(self._pause_button)
        toolbar_layout.addWidget(self._stop_button)
        toolbar_layout.addWidget(self._export_button)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(toolbar_widget)
        main_layout.addWidget(self._view, stretch=1)

        container = QWidget()
        container.setLayout(main_layout)
        self.setWidget(container)

    def _make_tool_button(self, tooltip: str, icon_path: str) -> QToolButton:
        btn = QToolButton()
        btn.setIcon(QIcon(QPixmap(icon_path)))
        btn.setToolTip(tooltip)
        btn.setAutoRaise(True)
        btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        return btn

    def _init_connection(self):
        self._new_button.clicked.connect(self._on_start_recording)
        self._resume_button.clicked.connect(self._on_resume_recording)
        self._pause_button.clicked.connect(self._on_pause_recording)
        self._stop_button.clicked.connect(self._on_stop_recording)
        self._export_button.clicked.connect(self._on_export_recording)

        self._view._ui.fileSelectionTableView.selectionModel().selectionChanged.connect(
            self._update_buttons
        )

    def _on_start_recording(self):
        console_item = GRPCRecorderConsoleItem("Recording", self._client)
        self._model.add_item(console_item)
        console_item.start()

    def _on_resume_recording(self):
        console_item = self._get_current_console_item()
        console_item.start()
        self._update_buttons()

    def _on_pause_recording(self):
        console_item = self._get_current_console_item()
        console_item.stop()
        self._update_buttons()

    def _on_stop_recording(self):
        index = self._view._ui.fileSelectionTableView.selectionModel().currentIndex()
        self._view.delete_file_selector_at_index(index)

    def _on_export_recording(self):
        console_item = self._get_current_console_item()
        assert console_item

        code_generator = CodeGenerator()
        script_text = code_generator.generate(console_item.get_events())

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Python Script",
            "recording.py",
            "Python Files (*.py)",
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(script_text)

    def _update_buttons(self):
        console_item = self._get_current_console_item()

        self._new_button.setEnabled(True)
        self._resume_button.setEnabled(
            not console_item.is_running() if console_item else False
        )
        self._pause_button.setEnabled(
            console_item.is_running() if console_item else False
        )
        self._stop_button.setEnabled(console_item is not None)
        self._export_button.setEnabled(console_item is not None)

    def _get_current_console_item(self) -> GRPCRecorderConsoleItem:
        index = self._view._ui.fileSelectionTableView.selectionModel().currentIndex()
        console_item = self._view._files_proxy_model.data(
            index, role=Qt.ItemDataRole.UserRole + 1
        )
        return console_item
