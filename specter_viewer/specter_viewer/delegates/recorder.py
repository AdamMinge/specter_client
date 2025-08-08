from PySide6.QtWidgets import (
    QWidget,
    QStyledItemDelegate,
    QApplication,
    QStyle,
    QStyleOptionViewItem,
    QTreeWidget,
)
from PySide6.QtGui import QIcon, QPainter, QCursor, QColor
from PySide6.QtCore import (
    QModelIndex,
    QAbstractItemModel,
    QPersistentModelIndex,
    Signal,
    QRect,
    QEvent,
)


class RecorderWidgetDelegate(QStyledItemDelegate):
    deleteHoverItem = Signal(QModelIndex)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.icon_size = QApplication.style().pixelMetric(
            QStyle.PixelMetric.PM_LargeIconSize
        )

        self.trash_icon = QApplication.style().standardIcon(
            QStyle.StandardPixmap.SP_TitleBarCloseButton
        )

        self.hovering_del_btn = False

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        super().paint(painter, option, index)

        option_state: QStyle.StateFlag = option.state
        option_rect: QRect = option.rect

        self.icon_size = option_rect.height() - 10

        if option_state & (
            QStyle.StateFlag.State_MouseOver | (QStyle.StateFlag.State_Selected)
        ):
            painter.save()
            icon_rect = QRect(
                option_rect.right() - self.icon_size,
                option_rect.top() + (option_rect.height() - self.icon_size) // 2,
                self.icon_size,
                self.icon_size,
            )
            option_widget: QWidget = option.widget
            mouse_pos = option_widget.mapFromGlobal(QCursor.pos())
            if icon_rect.contains(mouse_pos):
                painter.fillRect(icon_rect, QColor(0, 0, 0, 150))

            QIcon.paint(
                self.trash_icon,
                painter,
                icon_rect,
                mode=QIcon.Mode.Normal,
                state=QIcon.State.On,
            )

            painter.restore()

    def editorEvent(
        self,
        event: QEvent,
        model: QAbstractItemModel,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:

        event_pos = event.position()
        global_pos = event_pos.toPoint()
        option_widget: QTreeWidget = option.widget
        option_rect: QRect = option.rect

        if event.type() == QEvent.Type.MouseButtonPress:
            option_rect: QRect = option.rect
            icon_rect = QRect(
                option_rect.right() - self.icon_size,
                option_rect.top(),
                self.icon_size,
                self.icon_size,
            )

            if icon_rect.contains(global_pos):
                self.deleteHoverItem.emit(index)
                event.setAccepted(True)
                return True

        elif event.type() == QEvent.Type.MouseMove:
            icon_rect = QRect(
                option_rect.right() - self.icon_size,
                option_rect.top() + (option_rect.height() - self.icon_size) // 2,
                self.icon_size,
                self.icon_size,
            )

            if icon_rect.contains(global_pos):
                if not self.hovering_del_btn:
                    self.hovering_del_btn = True
                    option_widget.viewport().update()
                return True
            elif self.hovering_del_btn:
                self.hovering_del_btn = False
                option_widget.viewport().update()

        return super().editorEvent(event, model, option, index)
