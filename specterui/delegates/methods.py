import typing

from PySide6.QtWidgets import (
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyle,
    QApplication,
    QStyleOptionViewItem,
)
from PySide6.QtCore import (
    Qt,
    QEvent,
    QObject,
    QModelIndex,
    QAbstractItemModel,
    QSortFilterProxyModel,
)
from PySide6.QtGui import QPainter

from specterui.models import MethodListModel


class MethodButtonDelegate(QStyledItemDelegate):
    def __init__(self, parent: typing.Optional[QObject] = None):
        super().__init__(parent)

    def _get_base_model_and_index(
        self, current_model: QAbstractItemModel, current_index: QModelIndex
    ) -> typing.Tuple[typing.Optional[MethodListModel], QModelIndex]:
        if isinstance(current_model, MethodListModel):
            return current_model, current_index
        elif isinstance(current_model, QSortFilterProxyModel):
            source_index = current_model.mapToSource(current_index)
            source_model = current_model.sourceModel()
            if source_model:
                return self._get_base_model_and_index(source_model, source_index)
            return None, QModelIndex()
        else:
            return None, QModelIndex()

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ):
        if index.column() == 1 and index.data(
            MethodListModel.CustomDataRoles.ButtonRole
        ):
            button_option = QStyleOptionButton()
            button_option.rect = option.rect
            button_option.text = index.data(Qt.ItemDataRole.DisplayRole)
            button_option.state = QStyle.State_Enabled | QStyle.State_Active

            if option.state & QStyle.State_Selected:
                button_option.state |= QStyle.State_MouseOver

            QApplication.style().drawControl(
                QStyle.CE_PushButton, button_option, painter
            )
        else:
            super().paint(painter, option, index)

    def editorEvent(
        self,
        event: QEvent,
        model: QAbstractItemModel,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        if (
            index.column() == 1
            and index.data(MethodListModel.CustomDataRoles.ButtonRole)
            and event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            if option.rect.contains(event.pos()):
                base_model, base_index = self._get_base_model_and_index(model, index)

                if base_model and base_index.isValid():
                    base_model.call_method_at_index(base_index)
                    return True
        return super().editorEvent(event, model, option, index)
