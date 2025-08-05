import os
import enum
import typing

from PySide6.QtWidgets import (
    QWizardPage,
    QWizard,
    QCheckBox,
    QHBoxLayout,
    QVBoxLayout,
    QButtonGroup,
    QFileDialog,
    QLineEdit,
    QPushButton,
    QToolButton,
    QLabel,
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QSize, Slot

from specter.client import Client, attach_to_existing_process, attach_to_new_process

from specter_viewer import constants
from specter_viewer.widgets import ProcessTable


class AttachToNewProcessPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self._init_ui()
        self._register_fileds()

    def _init_ui(self):
        self.setTitle("Attach to New Process")

        self._application_path = QLineEdit(self)
        self._application_path.setPlaceholderText("Enter path to application...")
        self._browse_application = QPushButton("Browse")

        self._subprocess_name = QLineEdit(self)
        self._subprocess_name.setPlaceholderText("Enter optional subprocess name...")

        path_layout = QHBoxLayout()
        path_layout.addWidget(self._application_path)
        path_layout.addWidget(self._browse_application)

        layout = QVBoxLayout()
        layout.addLayout(path_layout)
        layout.addWidget(QLabel("Optional: Subprocess Name"))
        layout.addWidget(self._subprocess_name)

        self.setLayout(layout)

        self._browse_application.pressed.connect(self._handle_browse_pressed)

    def _register_fileds(self):
        self.registerField(
            "application_path*",
            self._application_path,
            "text",
            self._application_path.textChanged,
        )

        self.registerField("subprocess_name", self._subprocess_name)

    @Slot()
    def _handle_browse_pressed(self):
        if os.name == "nt":
            file_filter = "Executable Files (*.exe);;All Files (*)"
        else:
            file_filter = "Executable Files (*);;All Files (*)"

        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter(file_filter)
        file_path, _ = file_dialog.getOpenFileName(
            self, "Select Application", "", file_filter
        )
        if file_path:
            self._application_path.setText(file_path)

    def nextId(self):
        return Pages.Page_Invalid


class AttachToExistingProcessPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self._init_ui()
        self._register_fileds()

    def _init_ui(self):
        self.setTitle("Attach to Existing Process")

        self._filter_processes = QLineEdit(self)
        self._filter_processes.setPlaceholderText("Filter Processes")

        self._process_table = ProcessTable()
        self._process_table.refresh()

        self._refresh_button = QToolButton(self)
        self._refresh_button.setText("Refresh")
        self._refresh_button.setToolTip("Refresh process list")
        self._refresh_button.setIcon(QIcon(QPixmap(":/icons/refresh.png")))
        self._refresh_button.setIconSize(QSize(32, 32))

        self._layout = QVBoxLayout()
        self._layout.addWidget(self._filter_processes)
        self._layout.addWidget(self._process_table)
        self._layout.addWidget(self._refresh_button)
        self._layout.addWidget(self._refresh_button)
        self.setLayout(self._layout)

        self._filter_processes.textChanged.connect(self._handle_filter_changed)
        self._refresh_button.pressed.connect(self._handle_refresh_pressed)

    def _register_fileds(self):
        self.registerField(
            "selected_process*",
            self._process_table,
            "current",
            self._process_table.current_changed,
        )

    @Slot()
    def _handle_refresh_pressed(self):
        self._process_table.refresh()

    @Slot()
    def _handle_filter_changed(self):
        filter = self._filter_processes.text().lower()
        self._process_table.filter(filter)

    def nextId(self):
        return Pages.Page_Invalid


class AttachModeSelectionPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        self.setTitle("Select Attach Mode")

        self._new_process_checkbox = QCheckBox()
        self._new_process_checkbox.setText("Attach to new process")
        self._new_process_checkbox.setIconSize(QSize(128, 128))
        self._new_process_checkbox.setIcon(
            QIcon(QPixmap(":/icons/attach_to_new_process.png"))
        )

        self._existing_process_checkbox = QCheckBox()
        self._existing_process_checkbox.setText("Attach to existing process")
        self._existing_process_checkbox.setIconSize(QSize(128, 128))
        self._existing_process_checkbox.setIcon(
            QIcon(QPixmap(":/icons/attach_to_existing_process.png"))
        )

        self._layout = QVBoxLayout()
        self._layout.addWidget(self._new_process_checkbox)
        self._layout.addWidget(self._existing_process_checkbox)
        self.setLayout(self._layout)

        self.button_group = QButtonGroup(self)
        self.button_group.addButton(self._new_process_checkbox, 1)
        self.button_group.addButton(self._existing_process_checkbox, 2)
        self._new_process_checkbox.setChecked(True)

    def nextId(self):
        if self._new_process_checkbox.isChecked():
            return Pages.Page_AttachToNewProcess
        elif self._existing_process_checkbox.isChecked():
            return Pages.Page_AttachToExistingProcess
        return Pages.Page_Invalid


class Pages(enum.IntEnum):
    Page_Invalid = -1
    Page_AttachModeSelection = 0
    Page_AttachToExistingProcess = 1
    Page_AttachToNewProcess = 2


class AttachWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Attach Wizard")

        self.addPage(AttachModeSelectionPage())
        self.addPage(AttachToExistingProcessPage())
        self.addPage(AttachToNewProcessPage())

        self.setStartId(Pages.Page_AttachModeSelection)

    def attach(self) -> typing.Optional[Client]:
        if self.exec() != QWizard.Accepted:  # type: ignore
            return None

        if self.currentId() == Pages.Page_AttachToExistingProcess:
            selected_process = self.field("selected_process")
            assert selected_process

            return attach_to_existing_process(
                host=constants.SPECTERUI_SERVER_HOST,
                port=constants.SPECTERUI_SERVER_PORT,
                pid=selected_process.pid,
                library=constants.SPECTERUI_SERVER_DLL,
            )

        elif self.currentId() == Pages.Page_AttachToNewProcess:
            subprocess_name = self.field("subprocess_name")
            application_path = self.field("application_path")
            assert application_path

            return attach_to_new_process(
                host=constants.SPECTERUI_SERVER_HOST,
                port=constants.SPECTERUI_SERVER_PORT,
                app=application_path,
                library=constants.SPECTERUI_SERVER_DLL,
                subprocess_name=subprocess_name,
            )

        return None
