import datetime
import typing

from PySide6.QtWidgets import (
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyle,
    QApplication,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QDateTimeEdit,
)
from PySide6.QtCore import (
    Qt,
    QEvent,
    QDateTime,
)

from specterui.models import MethodTreeItem, MethodListModel, DataclassTreeItem


class MethodListDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        model = index.model()
        item = index.internalPointer()

        if isinstance(item, MethodTreeItem) and index.column() == 1:
            if model.data(index, MethodListModel.CustomDataRoles.ButtonRole):
                opt = QStyleOptionButton()
                opt.rect = option.rect
                opt.text = model.data(index, Qt.ItemDataRole.DisplayRole)
                opt.state = QStyle.StateFlag.State_Enabled
                if option.state & QStyle.StateFlag.State_MouseOver:
                    opt.state |= QStyle.StateFlag.State_MouseOver
                if option.state & QStyle.StateFlag.State_Sunken:
                    opt.state |= QStyle.StateFlag.State_Sunken

                QApplication.style().drawControl(
                    QStyle.ControlElement.CE_PushButton, opt, painter, None
                )
                return

        super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        item = index.internalPointer()

        if isinstance(item, MethodTreeItem) and index.column() == 1:
            if model.data(index, MethodListModel.CustomDataRoles.ButtonRole):
                if (
                    event.type() == QEvent.Type.MouseButtonRelease
                    and event.button() == Qt.MouseButton.LeftButton
                ):
                    if option.rect.contains(event.pos()):
                        if isinstance(model, MethodListModel):
                            model.call_Method_at_index(index)
                        return True

        return super().editorEvent(event, model, option, index)

    def createEditor(self, parent, option, index):
        model = index.model()
        item_type = model.data(index, MethodListModel.CustomDataRoles.TypeRole)
        field_item = model.data(index, MethodListModel.CustomDataRoles.TreeItemRole)

        if not isinstance(field_item, DataclassTreeItem) or field_item.field is None:
            return super().createEditor(parent, option, index)

        if item_type is bool:
            editor = QCheckBox(parent)
            editor.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            return editor
        elif item_type is int:
            editor = QSpinBox(parent)
            editor.setRange(-2147483647, 2147483647)
            return editor
        elif item_type is float:
            editor = QDoubleSpinBox(parent)
            editor.setRange(-1.7976931348623157e308, 1.7976931348623157e308)
            editor.setDecimals(6)
            return editor
        elif item_type is str:
            return QLineEdit(parent)
        elif item_type is datetime.datetime:
            editor = QDateTimeEdit(parent)
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd-MM-yyyy HH:mm:ss")
            return editor
        elif typing.get_origin(item_type) is list:
            return QLineEdit(parent)
        else:
            return QLineEdit(parent)

    def setEditorData(self, editor, index):
        model = index.model()
        value = model.data(index, Qt.ItemDataRole.EditRole)
        item_type = model.data(index, MethodListModel.CustomDataRoles.TypeRole)

        if item_type is bool:
            editor.setChecked(bool(value))
        elif item_type is int:
            editor.setValue(int(value) if value is not None else 0)
        elif item_type is float:
            editor.setValue(float(value) if value is not None else 0.0)
        elif item_type is str:
            editor.setText(str(value) if value is not None else "")
        elif item_type is datetime.datetime:
            editor.setDateTime(
                value if value is not None else QDateTime.currentDateTime()
            )
        elif typing.get_origin(item_type) is list:
            editor.setText(", ".join(map(str, value)) if value is not None else "")
        else:
            editor.setText(str(value) if value is not None else "")

    def setModelData(self, editor, model, index):
        item_type = model.data(index, MethodListModel.CustomDataRoles.TypeRole)
        new_value = None

        try:
            if item_type is bool:
                new_value = editor.isChecked()
            elif item_type is int:
                new_value = editor.value()
            elif item_type is float:
                new_value = editor.value()
            elif item_type is str:
                new_value = editor.text()
            elif item_type is datetime.datetime:
                new_value = editor.dateTime().toPython()
            elif typing.get_origin(item_type) is list:
                text = editor.text()
                if text:
                    list_type_args = typing.get_args(item_type)
                    if list_type_args:
                        element_type = list_type_args[0]
                        try:
                            new_value = [
                                element_type(s.strip()) for s in text.split(",")
                            ]
                        except ValueError:
                            new_value = [s.strip() for s in text.split(",")]
                    else:
                        new_value = [s.strip() for s in text.split(",")]
                else:
                    new_value = []
            else:
                new_value = editor.text()
                if (
                    not new_value
                    and model.data(index, Qt.ItemDataRole.EditRole) is None
                ):
                    new_value = None

        except ValueError:
            return

        model.setData(index, new_value, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
