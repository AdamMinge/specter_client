from PySide6.QtWidgets import (
    QSizePolicy,
    QWidget,
    QVBoxLayout,
    QLabel,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QByteArray

from specter.proto.specter_pb2 import ObjectId
from specter.client import Client, StreamReader


class ViewerWidget(QWidget):
    def __init__(self, client: Client):
        super().__init__()
        self._client = client
        self._stream_reader = None
        self._current_pixmap = QPixmap()
        self._object_id = None
        self._init_ui()
        self.setWindowTitle("Viewer")

    def _init_ui(self):
        self.layout = QVBoxLayout()

        self._image_label = QLabel("No image loaded")
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self._image_label)

        self.setLayout(self.layout)

    def _display_image(self, preview_message):
        if not hasattr(preview_message, "image") or not preview_message.image:
            self._image_label.setText("No image data received.")
            self._current_pixmap = QPixmap()
            return

        image_bytes = preview_message.image
        q_byte_array = QByteArray(image_bytes)
        new_pixmap = QPixmap()

        if new_pixmap.loadFromData(q_byte_array):
            self._current_pixmap = new_pixmap
            self._scale_and_set_pixmap()
        else:
            self._image_label.setText("Failed to load image from bytes.")
            self._current_pixmap = QPixmap()

    def _scale_and_set_pixmap(self):
        if self._current_pixmap.isNull():
            return

        label_size = self._image_label.size()
        if label_size.isEmpty():
            self._image_label.setPixmap(self._current_pixmap)
            self._image_label.setText("")
            return

        scaled_pixmap = self._current_pixmap.scaled(
            label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._image_label.setPixmap(scaled_pixmap)
        self._image_label.setText("")

    def set_object(self, object_id: str):
        self._object_id = object_id

        if self._stream_reader:
            self._stream_reader.stop()

        if self._object_id is not None:
            self._stream_reader = StreamReader(
                stream=self._client.preview_stub.ListenPreview(
                    ObjectId(id=self._object_id)
                ),
                on_data=self._display_image,
            )
        else:
            self._stream_reader = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scale_and_set_pixmap()
