from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex


class MethodsModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.methods = []

    def rowCount(self, parent=QModelIndex()):
        return len(self.methods)

    def columnCount(self, parent=QModelIndex()):
        return 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        method = self.methods[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return method

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return "Method"
