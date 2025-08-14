from PySide6.QtWidgets import (
    QMenu,
    QWidget,
    QVBoxLayout,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
)
from PySide6.QtGui import (
    QPixmap,
    QWheelEvent,
    QMouseEvent,
    QKeySequence,
    QAction,
    QIcon,
)
from PySide6.QtCore import Qt, QByteArray, QMetaObject, Slot, Q_ARG

from specter.proto.specter_pb2 import ObjectId
from specter.client import Client, StreamReader


class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.zoom_factor = 1.25
        self._default_transform = self.transform()

        self.action_zoom_in = QAction("Zoom In", self)
        self.action_zoom_in.setShortcut(QKeySequence("Ctrl++"))
        self.action_zoom_in.setIcon(QIcon(QPixmap(":/icons/zoom_in.png")))
        self.action_zoom_in.triggered.connect(
            lambda: self.zoom_by_factor(self.zoom_factor)
        )

        self.action_zoom_out = QAction("Zoom Out", self)
        self.action_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        self.action_zoom_out.setIcon(QIcon(QPixmap(":/icons/zoom_out.png")))
        self.action_zoom_out.triggered.connect(
            lambda: self.zoom_by_factor(1 / self.zoom_factor)
        )

        self.action_zoom_to_fit = QAction("Zoom to Fit", self)
        self.action_zoom_to_fit.setShortcut(QKeySequence("F"))
        self.action_zoom_to_fit.setIcon(QIcon(QPixmap(":/icons/zoom_to_fit.png")))
        self.action_zoom_to_fit.triggered.connect(self.zoom_to_fit)

        self.action_reset_view = QAction("Reset Camera", self)
        self.action_reset_view.setShortcut(QKeySequence("R"))
        self.action_reset_view.setIcon(QIcon(QPixmap(":/icons/zoom_clear.png")))
        self.action_reset_view.triggered.connect(self.reset_view)

        self.addAction(self.action_zoom_in)
        self.addAction(self.action_zoom_out)
        self.addAction(self.action_zoom_to_fit)
        self.addAction(self.action_reset_view)

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self.zoom_by_factor(self.zoom_factor)
        else:
            self.zoom_by_factor(1 / self.zoom_factor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            fake_event = QMouseEvent(
                QMouseEvent.MouseButtonPress,
                event.position(),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            super().mousePressEvent(fake_event)
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            fake_event = QMouseEvent(
                QMouseEvent.MouseButtonRelease,
                event.position(),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            super().mouseReleaseEvent(fake_event)
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction(self.action_zoom_in)
        menu.addAction(self.action_zoom_out)
        menu.addSeparator()
        menu.addAction(self.action_zoom_to_fit)
        menu.addAction(self.action_reset_view)
        menu.exec(event.globalPos())

    def zoom_to_fit(self):
        if not self.scene() or self.scene().sceneRect().isEmpty():
            return
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)

    def reset_view(self):
        self.setTransform(self._default_transform)

    def zoom_by_factor(self, factor: float):
        self.scale(factor, factor)


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
        self.layout = QVBoxLayout(self)

        self._scene = QGraphicsScene()
        self._view = ZoomableGraphicsView()
        self._view.setScene(self._scene)

        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        self.layout.addWidget(self._view)
        self.setLayout(self.layout)

    def _display_image(self, preview_message):
        QMetaObject.invokeMethod(
            self,
            "_update_pixmap",
            Qt.QueuedConnection,
            Q_ARG("QVariant", preview_message),
        )

    @Slot("QVariant")
    def _update_pixmap(self, preview_message):
        if not hasattr(preview_message, "image") or not preview_message.image:
            self._current_pixmap = QPixmap()
            self._pixmap_item.setPixmap(QPixmap())
            return

        image_bytes = preview_message.image
        q_byte_array = QByteArray(image_bytes)
        new_pixmap = QPixmap()

        if new_pixmap.loadFromData(q_byte_array):
            self._current_pixmap = new_pixmap
            self._pixmap_item.setPixmap(self._current_pixmap)
            self._scene.setSceneRect(self._current_pixmap.rect())
        else:
            self._current_pixmap = QPixmap()
            self._pixmap_item.setPixmap(QPixmap())

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
