from PySide6.QtWidgets import (
    QMainWindow,
    QSizePolicy,
)
from PySide6.QtCore import Qt

from specterui.client import Client
from specterui.widgets import (
    MethodsDock,
    ObjectsDock,
    PropertiesDock,
    RecorderDock,
    EditorDock,
    ViewerWidget,
    ToolBar,
)


class MainWindow(QMainWindow):
    def __init__(self, client: Client):
        super().__init__()
        self._client = client
        self._init_ui()
        self._init_connections()

    def _init_ui(self):
        self.setWindowTitle("SpecterUI App")
        self.resize(800, 600)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        self._objects_dock = ObjectsDock(self._client)
        self._properties_dock = PropertiesDock(self._client)
        self._methods_dock = MethodsDock(self._client)
        self._recorder_dock = RecorderDock(self._client)
        self._editor_dock = EditorDock(self._client)
        self._viewer_widget = ViewerWidget(self._client)

        self.setCentralWidget(self._viewer_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._objects_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._properties_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._methods_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._recorder_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._editor_dock)

        self.tabifyDockWidget(self._methods_dock, self._properties_dock)
        self.tabifyDockWidget(self._recorder_dock, self._editor_dock)

        self._toolbar = ToolBar(self._client)
        self.addToolBar(self._toolbar)

    def _init_connections(self):
        self._objects_dock.current_object_changed.connect(
            self._on_current_object_changed
        )

    def _on_current_object_changed(self, object_id: str):
        self._properties_dock.set_object(object_id)
        self._methods_dock.set_object(object_id)
        self._viewer_widget.set_object(object_id)
