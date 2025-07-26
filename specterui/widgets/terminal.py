from PySide6.QtWidgets import (
    QDockWidget,
)


class TerminalDock(QDockWidget):
    def __init__(self):
        super().__init__("Terminal")
