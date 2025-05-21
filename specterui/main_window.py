from PySide6.QtWidgets import (
    QMainWindow,
    QSizePolicy,
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTableView,
    QTreeView,
    QHeaderView,
)
from PySide6.QtCore import Signal, Qt, QAbstractItemModel

from pyside6_utils.widgets import DataClassTreeView
from pyside6_utils.models import DataclassModel

from specterui.client import Client


class ObjectsDock(QDockWidget):
    selected_object = Signal(str)

    def __init__(self, client: Client):
        super().__init__("Objects")
        self._client = client
        self._init_ui()
        self._init_connection()

    def _init_ui(self):
        self._model = QAbstractItemModel()
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
        pass


class PropertiesDock(QDockWidget):
    def __init__(self, client: Client):
        super().__init__("Properties")
        self._client = client
        self._init_ui()

    def _init_ui(self):
        self._model = DataclassModel()
        self._view = DataClassTreeView()
        self._view.setModel(self._model)
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


class MethodsDock(QDockWidget):
    def __init__(self):
        super().__init__("Methods")
        self._init_ui()

    def _init_ui(self):
        self._model = QAbstractItemModel()
        self._view = QTableView()
        self._view.setModel(self._model)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setAlternatingRowColors(True)
        self._view.horizontalHeader().setHidden(True)

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self._view)
        container.setLayout(layout)
        self.setWidget(container)


class RecorderDock(QDockWidget):
    def __init__(self):
        super().__init__("Recorder")


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
        self._methods_dock = MethodsDock()
        self._terminal_dock = TerminalDock()
        self._recorder_dock = RecorderDock()

        self.setCentralWidget(ViewerWidget())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._objects_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._properties_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._methods_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._terminal_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._recorder_dock)

        self.tabifyDockWidget(self._terminal_dock, self._recorder_dock)

    def _init_connnection(self):
        pass
