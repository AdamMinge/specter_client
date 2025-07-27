from PySide6.QtCore import QObject, Signal


class Context(QObject):
    current_object_changed = Signal(str)
    current_object_updated = Signal(str)

    def __init__(self):
        super().__init__()
        self._current_object = None

    @property
    def current_object(self) -> str:
        return self._current_object

    def set_current_object(self, object: str):
        if self._current_object == object:
            return

        self._current_object = object
        self.current_object_changed.emit(self._current_object)

    def update_current_object(self, object: str):
        if self._current_object == object:
            return

        self._current_object = object
        self.current_object_updated.emit(self._current_object)
