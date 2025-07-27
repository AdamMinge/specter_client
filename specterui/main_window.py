from PySide6.QtWidgets import (
    QMainWindow,
    QSizePolicy,
)
from PySide6.QtCore import Qt

from specterui.client import Client
from specterui.context import Context
from specterui.widgets import (
    MethodsDock,
    ObjectsDock,
    PropertiesDock,
    RecorderDock,
    TerminalDock,
    ViewerWidget,
    ToolBar,
)


class MainWindow(QMainWindow):
    def __init__(self, client: Client):
        super().__init__()
        self._client = client
        self._context = Context()
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("SpecterUI App")
        self.resize(800, 600)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        self._objects_dock = ObjectsDock(self._client, self._context)
        self._properties_dock = PropertiesDock(self._client, self._context)
        self._methods_dock = MethodsDock(self._client, self._context)
        self._terminal_dock = TerminalDock()
        self._recorder_dock = RecorderDock(self._client, self._context)
        self._viewer_widget = ViewerWidget(self._client, self._context)

        self.setCentralWidget(self._viewer_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._objects_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._properties_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._methods_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._terminal_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._recorder_dock)

        self.tabifyDockWidget(self._terminal_dock, self._recorder_dock)

        self._toolbar = ToolBar(self._client)
        self.addToolBar(self._toolbar)
