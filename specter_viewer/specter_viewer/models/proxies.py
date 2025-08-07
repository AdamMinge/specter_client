import math
import numbers
import typing

from PySide6.QtCore import (
    Qt,
    QModelIndex,
    QPersistentModelIndex,
    QAbstractItemModel,
    QObject,
    QSortFilterProxyModel,
)


FilterFunctionType = typing.Callable[
    [int, QModelIndex | QPersistentModelIndex, QAbstractItemModel], bool
]


class MultiColumnSortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QObject | None = ...) -> None:
        super().__init__(parent)
        self._sort_columns: list[int] = []
        self._sort_orders: list[Qt.SortOrder] = []
        self._filter_functions: typing.Dict[str, FilterFunctionType] = {}

    def _val_less_than(self, leftval, rightval):
        if leftval is None or (
            isinstance(leftval, numbers.Number) and math.isnan(leftval)
        ):
            return True
        elif rightval is None or (
            isinstance(rightval, numbers.Number) and math.isnan(rightval)
        ):
            return False
        return leftval < rightval

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        if len(self._sort_columns) == 0:
            return super().lessThan(left, right)
        else:
            for column, order in zip(self._sort_columns, self._sort_orders):
                left = self.sourceModel().index(left.row(), column)
                right = self.sourceModel().index(right.row(), column)
                leftval = left.data(role=Qt.ItemDataRole.EditRole)
                rightval = right.data(role=Qt.ItemDataRole.EditRole)
                if self._val_less_than(leftval, rightval) == self._val_less_than(
                    leftval=rightval, rightval=leftval
                ):
                    continue
                else:
                    return (
                        self._val_less_than(leftval, rightval)
                        if order == Qt.SortOrder.AscendingOrder
                        else self._val_less_than(leftval, rightval)
                    )

        return False

    def sort_by_columns(
        self, columns: list[int], orders: list[Qt.SortOrder] | None = None
    ) -> None:
        if orders is None or orders == []:
            orders = [Qt.SortOrder.AscendingOrder] * len(columns)
        self._sort_columns = columns
        self._sort_orders = orders
        self.invalidate()

    def set_filter_function(self, function_name: str, function: FilterFunctionType):
        invalidate = False
        if function_name in self._filter_functions:
            invalidate = True
        self._filter_functions[function_name] = function
        if invalidate:
            self.invalidateFilter()

    def clear_function_filters(self):
        self._filter_functions = {}
        self.invalidateFilter()

    def get_filter_functions(self) -> typing.Dict[str, FilterFunctionType]:
        return self._filter_functions

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        if not super().filterAcceptsRow(source_row, source_parent):
            return False
        for function in self._filter_functions.values():
            try:
                if not function(source_row, source_parent, self.sourceModel()):
                    return False
            except Exception:
                return False
        return True
