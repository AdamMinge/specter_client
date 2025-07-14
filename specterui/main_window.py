import typing

from PySide6.QtWidgets import (
    QMainWindow,
    QSizePolicy,
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTableView,
    QTreeView,
    QHeaderView,
    QToolButton,
    QHBoxLayout
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Signal, Qt, QModelIndex

from pyside6_utils.widgets import DataClassTreeView, ConsoleWidget
from pyside6_utils.models.console_widget_models.console_model import ConsoleModel

from specterui.client import Client
from specterui.models import GRPCObjectsModel, GRPCPropertiesModel, FilteredPropertiesProxyModel, GRPCRecorderConsoleItem


class ObjectsDock(QDockWidget):
    selected_object = Signal(str)

    def __init__(self, client: Client):
        super().__init__("Objects")
        self._client = client
        self._init_ui()
        self._init_connection()

    def _init_ui(self):
        self._model = GRPCObjectsModel(self._client)
        self._view = QTreeView()
        self._view.setModel(self._model)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setAlternatingRowColors(True)

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self._view)
        container.setLayout(layout)
        self.setWidget(container)

    def _init_connection(self):
        self._view.selectionModel().currentChanged.connect(self._on_selection_changed)
        self._model.dataChanged.connect(self._on_data_changed)

    def _on_selection_changed(self, current: QModelIndex, _: QModelIndex):
        query = None
        if current.isValid():
            query = self._model.data(
                current.sibling(current.row(), GRPCObjectsModel.Columns.Query),
                Qt.ItemDataRole.UserRole,
            )

        self.selected_object.emit(query)

    def _on_data_changed(self, topLeft: QModelIndex, bottomRight: QModelIndex, roles=None):
        current_index = self._view.currentIndex()

        if not current_index.isValid():
            return
        
        if current_index.parent() != topLeft.parent():
            return

        if (topLeft.row() <= current_index.row() <= bottomRight.row() and
            topLeft.column() <= current_index.column() <= bottomRight.column()):

            query = self._model.data(
                current_index.sibling(current_index.row(), GRPCObjectsModel.Columns.Query),
                Qt.ItemDataRole.UserRole,
            )

            self.selected_object.emit(query)


class PropertiesDock(QDockWidget):
    def __init__(self, client: Client):
        super().__init__("Properties")
        self._client = client
        self._init_ui()

    def _init_ui(self):
        self._model = GRPCPropertiesModel(self._client)
        self._proxy_model = FilteredPropertiesProxyModel()
        self._proxy_model.setSourceModel(self._model)
        self._view = DataClassTreeView()
        self._view.setModel(self._proxy_model)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setAlternatingRowColors(True)
        self._view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._view.header().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self._view)
        container.setLayout(layout)
        self.setWidget(container)

    def set_object(self, query: typing.Optional[str]):
        self._proxy_model.setSourceModel(None)  
        self._model.set_object(query)
        self._proxy_model.setSourceModel(self._model)


class MethodsDock(QDockWidget):
    def __init__(self, client: Client):
        super().__init__("Methods")
        self._client = client
        self._init_ui()

    def _init_ui(self):
        #self._model = GRPCMethodsModel(self._client)
        self._view = QTableView()
        #self._view.setModel(self._model)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setAlternatingRowColors(True)
        self._view.horizontalHeader().setHidden(True)

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self._view)
        container.setLayout(layout)
        self.setWidget(container)

    def set_object(self, query: typing.Optional[str]):
        pass


class RecorderDock(QDockWidget):
    def __init__(self, client: Client):
        super().__init__("Recorder")
        self._client = client
        self._init_ui()
        self._init_connection()
        self._update_buttons()

    def _init_ui(self):
        self._model = ConsoleModel()
        self._view = ConsoleWidget(ui_text_min_update_interval=0.1, display_max_blocks=5000)
        self._view.set_model(self._model)
        self._view.set_console_width_percentage(80)

        self._new_button = self._make_tool_button("New", ":/icons/start.png")
        self._resume_button = self._make_tool_button("Resume", ":/icons/resume.png")
        self._pause_button = self._make_tool_button("Pause", ":/icons/pause.png")
        self._stop_button = self._make_tool_button("Stop", ":/icons/stop.png")

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        toolbar_layout.addWidget(self._new_button)
        toolbar_layout.addWidget(self._resume_button)
        toolbar_layout.addWidget(self._pause_button)
        toolbar_layout.addWidget(self._stop_button)

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

        self._view.ui.fileSelectionTableView.selectionModel().selectionChanged.connect(self._update_buttons)

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
        index = self._view.ui.fileSelectionTableView.selectionModel().currentIndex()
        self._view.delete_file_selector_at_index(index)

    def _update_buttons(self):
        console_item = self._get_current_console_item()

        self._new_button.setEnabled(True)
        self._resume_button.setEnabled(not console_item.is_running() if console_item else False)
        self._pause_button.setEnabled(console_item.is_running() if console_item else False)
        self._stop_button.setEnabled(console_item is not None)

    def _get_current_console_item(self) -> GRPCRecorderConsoleItem:
        index = self._view.ui.fileSelectionTableView.selectionModel().currentIndex()
        console_item = self._view._files_proxy_model.data(index, role = Qt.ItemDataRole.UserRole + 1)
        return console_item


class TerminalDock(QDockWidget):
    def __init__(self):
        super().__init__("Terminal")


class ViewerWidget(QWidget):
    def __init__(self):
        super().__init__()


class MainWindow(QMainWindow):
    def __init__(self, client: Client):
        super().__init__()
        self._client = client
        self._init_ui()
        self._init_connnection()

    def _init_ui(self):
        self.setWindowTitle("SpecterUI App")
        self.resize(800, 600)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        self._objects_dock = ObjectsDock(self._client)
        self._properties_dock = PropertiesDock(self._client)
        self._methods_dock = MethodsDock(self._client)
        self._terminal_dock = TerminalDock()
        self._recorder_dock = RecorderDock(self._client)

        self.setCentralWidget(ViewerWidget())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._objects_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._properties_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._methods_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._terminal_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._recorder_dock)

        self.tabifyDockWidget(self._terminal_dock, self._recorder_dock)

    def _init_connnection(self):
        self._objects_dock.selected_object.connect(self._properties_dock.set_object)
        self._objects_dock.selected_object.connect(self._methods_dock.set_object)