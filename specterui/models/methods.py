import dataclasses
import datetime
import typing
import enum

from PySide6.QtGui import QFont, QBrush, QColor

from PySide6.QtCore import (
    Qt,
    QModelIndex,
    QAbstractItemModel,
    Signal,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
)

from specterui.proto.specter_pb2 import Object, Method, MethodCall

from specterui.client import Client, convert_to_value, convert_from_value
from specterui.context import Context
from specterui.models.utils import (
    flatten_dict_field,
    unflatten_dict_field,
    create_properties_dataclass,
)


class BaseTreeItem:
    def __init__(self, name: str, parent: typing.Optional["BaseTreeItem"] = None):
        self._name = name
        self._parent = parent
        self._children: typing.List["BaseTreeItem"] = []
        if parent is not None:
            parent.append_child(self)

    def append_child(self, child: "BaseTreeItem"):
        self._children.append(child)

    def child(self, row: int) -> typing.Optional["BaseTreeItem"]:
        if 0 <= row < len(self._children):
            return self._children[row]
        return None

    def child_count(self) -> int:
        return len(self._children)

    def parent(self) -> typing.Optional["BaseTreeItem"]:
        return self._parent

    def row(self) -> int:
        if self._parent:
            try:
                return self._parent._children.index(self)
            except ValueError:
                pass
        return 0

    @property
    def name(self) -> str:
        return self._name

    def find_ancestor(self, ancestor_type: type) -> typing.Optional[typing.Any]:
        current = self
        while current:
            if isinstance(current, ancestor_type):
                return current
            current = current.parent()
        return None


class DataclassTreeItem(BaseTreeItem):
    def __init__(
        self,
        name: str,
        field: typing.Optional[dataclasses.Field],
        parent: typing.Optional[BaseTreeItem],
    ):
        super().__init__(name, parent)
        self._field = field

    @property
    def field(self) -> typing.Optional[dataclasses.Field]:
        return self._field


class MethodTreeItem(BaseTreeItem):
    def __init__(
        self,
        name: str,
        dataclass_instance: object,
        call_action: typing.Callable[[], None],
        parent: typing.Optional[BaseTreeItem],
    ):
        super().__init__(name, parent)
        self._dataclass_instance = dataclass_instance
        self._call_action = call_action

    @property
    def dataclass_instance(self) -> object:
        return self._dataclass_instance

    @property
    def call_action(self) -> typing.Callable[[], None]:
        return self._call_action


class HasNoDefaultError(Exception):
    """Raised when a field has no default value"""


class MethodListModel(QAbstractItemModel):
    class CustomDataRoles(enum.IntEnum):
        TypeRole = Qt.ItemDataRole.UserRole
        FieldRole = Qt.ItemDataRole.UserRole + 1
        DefaultValueRole = Qt.ItemDataRole.UserRole + 2
        AttributeNameRole = Qt.ItemDataRole.UserRole + 3
        TreeItemRole = Qt.ItemDataRole.UserRole + 4
        ButtonRole = Qt.ItemDataRole.UserRole + 5

    MethodTriggered = Signal(str, object)

    def __init__(
        self,
        parent: typing.Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._root_node = BaseTreeItem("Root", None)
        self.set_methods([])

    def set_methods(
        self,
        method_data_list: typing.List[
            typing.Tuple[str, object, typing.Callable[[], None]]
        ],
    ):
        self._method_data_list = method_data_list
        self._setup_model()

    def _setup_model(self) -> None:
        self.beginResetModel()
        self._root_node._children.clear()

        for func_name, dc_instance, call_action in self._method_data_list:
            if not dataclasses.is_dataclass(dc_instance):
                continue

            func_tree_item = MethodTreeItem(
                func_name, dc_instance, call_action, self._root_node
            )

            data_hierarchy = {}
            for cur_field in dataclasses.fields(dc_instance):
                if "display_path" in cur_field.metadata:
                    path = cur_field.metadata["display_path"].split("/")
                    current_dict = data_hierarchy
                    for i, cur_path in enumerate(path):
                        if cur_path not in current_dict:
                            current_dict[cur_path] = {}
                        current_dict = current_dict[path[i]]
                    current_dict[cur_field.name] = {}
                else:
                    data_hierarchy[cur_field.name] = {}

            self._build_dataclass_sub_tree(dc_instance, data_hierarchy, func_tree_item)
        self.endResetModel()

    def _build_dataclass_sub_tree(
        self,
        dataclass_instance: object,
        data_hierarchy: typing.Dict,
        parent_tree_item: BaseTreeItem,
    ) -> None:
        name_field_dict = {
            field.name: field for field in dataclasses.fields(dataclass_instance)
        }
        for key, value in data_hierarchy.items():
            cur_field = name_field_dict.get(key, None)
            if cur_field:
                item = DataclassTreeItem(
                    name=key, field=cur_field, parent=parent_tree_item
                )
            else:
                item = DataclassTreeItem(name=key, field=None, parent=parent_tree_item)

            if isinstance(value, dict) and len(value) > 0:
                self._build_dataclass_sub_tree(dataclass_instance, value, item)

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        item = index.internalPointer()
        assert isinstance(item, BaseTreeItem)
        parent_item = item.parent()

        if parent_item == self._root_node or parent_item is None:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not parent.isValid():
            parent_item = self._root_node
        else:
            parent_item = parent.internalPointer()
        assert isinstance(parent_item, BaseTreeItem)
        return parent_item.child_count()

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 2

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> typing.Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if section == 0:
                    return "Name"
                elif section == 1:
                    return "Value / Action"
        return None

    def get_default_value(self, data_class_field: dataclasses.Field) -> typing.Any:
        if (
            hasattr(data_class_field, "default")
            and data_class_field.default != dataclasses.MISSING
        ):
            return data_class_field.default
        elif (
            hasattr(data_class_field, "default_factory")
            and data_class_field.default_factory != dataclasses.MISSING
        ):
            return data_class_field.default_factory()
        else:
            raise HasNoDefaultError(
                f"Could not get default value for field {data_class_field.name}"
            )

    def data(
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> typing.Any:
        if not index.isValid():
            return None

        item = index.internalPointer()
        assert isinstance(item, BaseTreeItem)

        if isinstance(item, MethodTreeItem):
            if role == Qt.ItemDataRole.DisplayRole:
                if index.column() == 0:
                    return item.name
                elif index.column() == 1:
                    return "Call"
            elif role == MethodListModel.CustomDataRoles.ButtonRole:
                if index.column() == 1:
                    return True
            elif role == MethodListModel.CustomDataRoles.TreeItemRole:
                return item
            return None

        elif isinstance(item, DataclassTreeItem):
            owning_method_item = item.find_ancestor(MethodTreeItem)
            if not owning_method_item or not owning_method_item.dataclass_instance:
                return None

            dataclass_instance = owning_method_item.dataclass_instance

            if item.field is None:
                if index.column() == 0:
                    if role == Qt.ItemDataRole.DisplayRole:
                        return item.name
                return None

            if role == Qt.ItemDataRole.DisplayRole:
                if index.column() == 0:
                    return item.field.metadata.get("display_name", item.name)
                else:
                    ret_val = getattr(dataclass_instance, item.name, None)
                    if ret_val is None:
                        return ""
                    elif isinstance(ret_val, datetime.datetime):
                        return ret_val.strftime("%d-%m-%Y %H:%M:%S")
                    elif isinstance(ret_val, bool):
                        return str(ret_val).capitalize()
                    elif isinstance(ret_val, list):
                        return ", ".join([str(item_val) for item_val in ret_val])
                    return ret_val
            elif role == Qt.ItemDataRole.EditRole:
                return getattr(dataclass_instance, item.name, None)
            elif role == Qt.ItemDataRole.ToolTipRole:
                result_str = item.field.metadata.get("help", "")
                if item.field.metadata.get("required", False):
                    result_str += " <b style='color:red'>(required)</b>"
                try:
                    item_type_name = item.field.type.__name__
                except AttributeError:
                    item_type_name = str(item.field.type)
                result_str += f" (type: {item_type_name[:20]})"
                try:
                    default_val_str = str(self.get_default_value(item.field))
                    result_str += f" (default: {default_val_str[:20]})"
                except HasNoDefaultError:
                    pass
                return result_str
            elif role == MethodListModel.CustomDataRoles.TypeRole:
                if typing.get_origin(item.field.type) is typing.Union and type(
                    None
                ) in typing.get_args(item.field.type):
                    return [
                        arg
                        for arg in typing.get_args(item.field.type)
                        if arg is not type(None)
                    ][0]
                return item.field.type
            elif role == MethodListModel.CustomDataRoles.AttributeNameRole:
                return item.name
            elif role == MethodListModel.CustomDataRoles.FieldRole:
                return item.field
            elif role == MethodListModel.CustomDataRoles.DefaultValueRole:
                return self.get_default_value(item.field)
            elif role == MethodListModel.CustomDataRoles.TreeItemRole:
                return item
            elif role == Qt.ItemDataRole.FontRole:
                try:
                    default_val = self.get_default_value(item.field)
                    cur_val = getattr(dataclass_instance, item.name, None)
                    if cur_val != default_val:
                        font = QFont()
                        font.setBold(True)
                        return font
                except HasNoDefaultError:
                    pass
                return None
            elif role == Qt.ItemDataRole.BackgroundRole:
                if (
                    item.field.metadata.get("required", False)
                    and getattr(dataclass_instance, item.name, None) is None
                ):
                    return QBrush(QColor(255, 0, 0, 50))
                return None
        return None

    def _set_data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: typing.Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not index.isValid():
            return False

        tree_item = index.internalPointer()
        assert isinstance(tree_item, BaseTreeItem)

        if isinstance(tree_item, MethodTreeItem):
            return False

        if isinstance(tree_item, DataclassTreeItem):
            if tree_item.field is None:
                return False

            owning_method_item = tree_item.find_ancestor(MethodTreeItem)
            if not owning_method_item or not owning_method_item.dataclass_instance:
                return False

            dataclass_instance = owning_method_item.dataclass_instance

            if role == Qt.ItemDataRole.EditRole:
                setattr(dataclass_instance, tree_item.name, value)
                self.dataChanged.emit(index, index)
                return True
            elif role == MethodListModel.CustomDataRoles.DefaultValueRole:
                try:
                    default_value = self.get_default_value(tree_item.field)
                    setattr(dataclass_instance, tree_item.name, default_value)
                    self.dataChanged.emit(index, index)
                    return True
                except HasNoDefaultError:
                    return False
        return False

    def setData(
        self,
        index: QModelIndex,
        value: typing.Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not index.isValid():
            return False

        item = index.internalPointer()
        assert isinstance(item, BaseTreeItem)

        if isinstance(item, MethodTreeItem):
            return False

        if isinstance(item, DataclassTreeItem) and item.field is not None:
            current_value = self.data(index, role)
            if current_value == value and role == Qt.ItemDataRole.EditRole:
                return False

            return self._set_data(index, value, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.NoItemFlags

        item = index.internalPointer()
        assert isinstance(item, BaseTreeItem)

        base_flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        if isinstance(item, MethodTreeItem):
            return base_flags
        elif isinstance(item, DataclassTreeItem):
            if item.field is None:
                return base_flags
            if index.column() == 0:
                return base_flags
            else:
                if item.field.metadata.get("editable", True):
                    base_flags |= Qt.ItemFlag.ItemIsEditable
                return base_flags
        return base_flags

    def index(
        self, row: int, column: int, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parent_item = self._root_node
        else:
            parent_item = parent.internalPointer()

        assert isinstance(parent_item, BaseTreeItem)
        child_item = parent_item.child(row)

        if child_item:
            return self.createIndex(row, column, child_item)
        else:
            return QModelIndex()

    def call_method_at_index(self, index: QModelIndex):
        if not index.isValid():
            return
        item = index.internalPointer()
        if isinstance(item, MethodTreeItem):
            item.call_action()
            self.MethodTriggered.emit(item.name, item.dataclass_instance)


class GRPCMethodsModel(MethodListModel):
    def __init__(self, client: Client, context: Context, parent=None):
        super().__init__(parent)

        self._client = client
        self._context = context

        self._init_connections()

    def _init_connections(self):
        self._context.current_object_changed.connect(self._on_current_object_changed)

    def _on_current_object_changed(self):
        self._fetch_initial_state()

    def _fetch_initial_state(self):
        if self._context.current_object is None:
            self.set_methods([])
            return False

        methods_data = []
        try:
            response = self._client.object_stub.GetMethods(
                Object(query=self._context.current_object)
            )
        except Exception as e:
            self.set_methods([])
            return False

        for method in response.methods:
            dataclass_instance = self._create_dataclass_instance(method)
            if dataclass_instance is None:
                continue

            call_method = self._create_call_method(method.name, dataclass_instance)
            methods_data.append((method.name, dataclass_instance, call_method))

        self.set_methods(methods_data)
        return True

    def _create_call_method(self, method_name, dataclass_instance):
        def call_method(method_name=method_name, dataclass_instance=dataclass_instance):
            root_fields = set()
            for field in dataclasses.fields(dataclass_instance):
                root_field = field.name.split("_", 1)[0]
                root_fields.add(root_field)

            arguments = []
            for root_field in root_fields:
                value_to_send = unflatten_dict_field(dataclass_instance, root_field)

                arguments.append(convert_to_value(value_to_send))

            self._client.object_stub.CallMethod(
                MethodCall(
                    object=Object(query=self._context.current_object),
                    method=method_name,
                    arguments=arguments,
                )
            )

        return call_method

    def _create_dataclass_instance(self, method: Method):
        fields = []
        values = {}

        for parameter in method.parameters:
            base_path = parameter.name
            base_value = convert_from_value(parameter.default_value)

            if base_value is None:
                return None

            prop_fields, prop_values = flatten_dict_field(
                base_value,
                base_path,
                field_prefix=base_path,
                editable=True,
            )
            fields.extend(prop_fields)
            values.update(prop_values)

        return create_properties_dataclass(fields, values)


class FilteredAttributeTypeProxyModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        source_model = self.sourceModel()
        index = source_model.index(source_row, 0, source_parent)
        if not index.isValid():
            return True

        item = index.data(MethodListModel.CustomDataRoles.TreeItemRole)
        return not (
            isinstance(item, DataclassTreeItem)
            and isinstance(item.name, str)
            and item.name.endswith("type")
        )
