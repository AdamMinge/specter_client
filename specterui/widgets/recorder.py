from PySide6.QtWidgets import (
    QSizePolicy,
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QToolButton,
    QHBoxLayout,
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt

from pyside6_utils.widgets import ConsoleWidget
from pyside6_utils.models.console_widget_models.console_model import ConsoleModel

from specterui.client import Client
from specterui.context import Context
from specterui.models import (
    GRPCRecorderConsoleItem,
)


class RecorderDock(QDockWidget):
    def __init__(self, client: Client, context: Context):
        super().__init__("Recorder")
        self._client = client
        self._context = context
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

        self._view.ui.fileSelectionTableView.selectionModel().selectionChanged.connect(
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
        index = self._view.ui.fileSelectionTableView.selectionModel().currentIndex()
        self._view.delete_file_selector_at_index(index)

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

    def _get_current_console_item(self) -> GRPCRecorderConsoleItem:
        index = self._view.ui.fileSelectionTableView.selectionModel().currentIndex()
        console_item = self._view._files_proxy_model.data(
            index, role=Qt.ItemDataRole.UserRole + 1
        )
        return console_item
