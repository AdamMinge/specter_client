import enum
import typing
import datetime
import dataclasses

from PySide6.QtCore import (
    Qt,
    QObject,
    QMetaObject,
    Slot,
    QModelIndex,
    QSortFilterProxyModel,
    QPersistentModelIndex,
    QAbstractItemModel,
    Q_ARG,
)
from PySide6.QtGui import QFont, QBrush, QColor

from specter.proto.specter_pb2 import ObjectId, PropertyUpdate
from specter.client import Client, StreamReader, convert_to_value, convert_from_value

from specter_viewer.models.utils import (
    ObservableDict,
    EmptyDataclass,
    flatten_dict_field,
    unflatten_dict_field,
    create_properties_dataclass,
)


class PropertiesTreeItem(object):
    def __init__(
        self,
        name: str,
        item_data: typing.Any,
        field: dataclasses.Field | None,
        parent: typing.Optional["PropertiesTreeItem"] = None,
    ) -> None:
        self.name = name
        self.item_data = item_data
        self.field = field
        self.parent_item = parent
        self.child_items = []

    def append_child(self, item: "PropertiesTreeItem") -> None:
        self.child_items.append(item)

    def child(self, row: int) -> "PropertiesTreeItem":
        return self.child_items[row]

    def child_count(self) -> int:
        return len(self.child_items)

    def column_count(self) -> int:
        return 2

    def data(self) -> typing.Any:
        return self.item_data

    def get_field(self) -> dataclasses.Field | None:
        return self.field

    def parent(self) -> "PropertiesTreeItem | None":
        return self.parent_item

    def row(self) -> int:
        if self.parent_item:
            return self.parent_item.child_items.index(self)
        return 0


class HasNoDefaultError(Exception):
    """Raised when a field has no default value"""


class PropertiesModel(QAbstractItemModel):
    class CustomDataRoles(enum.IntEnum):
        TypeRole = Qt.ItemDataRole.UserRole
        FieldRole = Qt.ItemDataRole.UserRole + 1
        DefaultValueRole = Qt.ItemDataRole.UserRole + 2
        AttributeNameRole = Qt.ItemDataRole.UserRole + 3
        TreeItemRole = Qt.ItemDataRole.UserRole + 4

    def __init__(
        self,
        dataclass_instance: object,
        parent: typing.Optional[QObject] = None,
        allow_non_field_attrs: bool = False,
    ) -> None:
        super().__init__(parent)
        self._allow_non_field_attrs = allow_non_field_attrs
        self.set_dataclass_instance(dataclass_instance)

    def set_dataclass_instance(self, dataclass_instance: typing.Any) -> None:
        if not dataclasses.is_dataclass(dataclass_instance):
            raise TypeError(
                f"Expected a dataclass instance, got {type(dataclass_instance)} - make sure @dataclass is"
                "used on the class definition"
            )

        dataclass_fields = dataclasses.fields(dataclass_instance)
        dataclass_field_names = [field.name for field in dataclass_fields]
        if not self._allow_non_field_attrs:
            for attr in dir(dataclass_instance):
                if not attr.startswith("__"):
                    if attr not in dataclass_field_names and not callable(
                        getattr(dataclass_instance, attr)
                    ):
                        raise AttributeError(
                            f"Attribute {attr} is not a field of the dataclass. "
                            "This most likely happened because "
                            " @dataclass decorator to the class definition"
                        )

        self.beginResetModel()

        self._dataclass = dataclass_instance
        self._root_node = PropertiesTreeItem("Root", None, None, None)

        self.data_hierachy = {}

        if dataclass_instance is None:
            self.modelReset.emit()
            self.endResetModel()
            return

        for cur_field in dataclasses.fields(self._dataclass):
            if "display_path" in cur_field.metadata:
                path = cur_field.metadata["display_path"].split("/")
                current_dict = self.data_hierachy
                for i, cur_path in enumerate(path):
                    if cur_path not in current_dict:
                        current_dict[cur_path] = {}
                    current_dict = current_dict[path[i]]
                current_dict[cur_field.name] = {}
            else:
                self.data_hierachy[cur_field.name] = {}

        self._build_tree(self._dataclass, self.data_hierachy, self._root_node)
        self.modelReset.emit()
        self.endResetModel()

    def get_dataclass(self) -> typing.Any:
        return self._dataclass

    def _build_tree(
        self,
        data: "DataclassInstance",  # type:ignore
        data_hierarchy: typing.Dict,
        parent: PropertiesTreeItem,
    ) -> None:
        name_field_dict = {field.name: field for field in dataclasses.fields(data)}
        for key, value in data_hierarchy.items():
            item_data = None
            if key in data.__dict__:
                item_data = data.__dict__[key]

            item = PropertiesTreeItem(
                name=key,
                item_data=item_data,
                field=name_field_dict.get(key, None),
                parent=parent,
            )
            parent.append_child(item)
            if isinstance(value, dict) and len(value) > 0:
                self._build_tree(data, value, item)

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        item = index.internalPointer()
        assert isinstance(item, PropertiesTreeItem)
        parent_item = item.parent()

        if parent_item == self._root_node or parent_item is None:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not parent.isValid():
            parent_item = self._root_node
        else:
            parent_item = parent.internalPointer()
        assert isinstance(parent_item, PropertiesTreeItem)
        return parent_item.child_count()

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> typing.Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if section == 0:
                    return "Property"
                elif section == 1:
                    return "Value"
            else:
                return section
        else:
            return None

    def get_default_value(self, data_class_field: dataclasses.Field) -> typing.Any:
        if (
            hasattr(data_class_field, "default")
            and data_class_field.default != dataclasses.MISSING
        ):
            return data_class_field.default
        elif hasattr(data_class_field, "default_factory"):
            return data_class_field.default_factory()  # type: ignore
        else:
            raise HasNoDefaultError(
                f"Could not get default value for field {data_class_field.name}"
            )

    def data(
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> typing.Any:
        if not index.isValid():
            return None

        node: PropertiesTreeItem = index.internalPointer()  # type: ignore
        name_field_dict = {
            field.name: field for field in dataclasses.fields(self._dataclass)
        }

        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                try:
                    return name_field_dict[node.name].metadata["display_name"]
                except (IndexError, KeyError, AttributeError):
                    return node.name
            else:
                ret_val = self._dataclass.__dict__.get(node.name, None)
                if ret_val is None:
                    return ""
                elif isinstance(ret_val, datetime.datetime):
                    return ret_val.strftime("%d-%m-%Y %H:%M:%S")
                elif isinstance(ret_val, bool):
                    return str(ret_val).capitalize()
                elif isinstance(ret_val, list):
                    return ", ".join([str(item) for item in ret_val])
                return ret_val
        elif role == Qt.ItemDataRole.EditRole:
            return self._dataclass.__dict__.get(node.name, None)
        elif role == Qt.ItemDataRole.ToolTipRole:
            if name_field_dict.get(node.name, None) is None:
                return node.name
            result_str = ""
            result_str += name_field_dict[node.name].metadata.get("help", "")

            if name_field_dict[node.name].metadata.get("required", False):
                result_str += " <b style='color:red'>(required)</b>"
            try:
                item_type_name = name_field_dict[node.name].type.__name__
            except AttributeError:
                item_type_name = str(name_field_dict[node.name].type)
            result_str += f" (type: {item_type_name[:20]})"

            try:
                result_str += f" (default: {str(self.get_default_value(name_field_dict[node.name]))[:20]})"
            except HasNoDefaultError:
                pass

            return result_str
        elif role == PropertiesModel.CustomDataRoles.TypeRole:
            result = name_field_dict.get(node.name, None)
            if result:
                return result.type
            else:
                return None
        elif role == PropertiesModel.CustomDataRoles.AttributeNameRole:
            return node.name
        elif role == PropertiesModel.CustomDataRoles.FieldRole:
            result = name_field_dict.get(node.name, None)
            return result
        elif role == PropertiesModel.CustomDataRoles.DefaultValueRole:
            if name_field_dict.get(node.name, None) is None:
                raise HasNoDefaultError(
                    f"Field {node.name} is not a field of the dataclass"
                )
            return self.get_default_value(name_field_dict[node.name])
        elif role == PropertiesModel.CustomDataRoles.TreeItemRole:
            return node
        elif role == Qt.ItemDataRole.FontRole:
            if name_field_dict.get(node.name, None) is None:
                return None

            default_val = None

            default_val = self.get_default_value(name_field_dict[node.name])
            cur_val = self._dataclass.__dict__.get(node.name, None)

            if cur_val != default_val:
                font = QFont()
                font.setBold(True)
                return font
            return None
        elif role == Qt.ItemDataRole.BackgroundRole:
            if name_field_dict.get(node.name, None) is None:
                return None
            if hasattr(name_field_dict[node.name], "metadata"):
                is_required = name_field_dict[node.name].metadata.get("required", False)
                if (
                    is_required
                    and self._dataclass.__dict__.get(node.name, None) is None
                ):
                    return QBrush(QColor(255, 0, 0, 50))
            return None

        return None

    def setData(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: typing.Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if role == Qt.ItemDataRole.EditRole:
            tree_item = index.internalPointer()
            assert isinstance(tree_item, PropertiesTreeItem)
            self._dataclass.__dict__[tree_item.name] = value
            self.dataChanged.emit(index, index)
            return True
        if role == PropertiesModel.CustomDataRoles.DefaultValueRole:
            tree_item = index.internalPointer()
            assert isinstance(
                tree_item, PropertiesTreeItem
            ), "Can't get default value for non-treeitem"
            assert (
                tree_item.field is not None
            ), "Can't get default value for property without field"
            self._dataclass.__dict__[tree_item.name] = self.get_default_value(
                tree_item.field
            )
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if index.column() == 0:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        else:
            if index.internalPointer():
                node = index.internalPointer()
                assert isinstance(node, PropertiesTreeItem)
                if node.field:
                    flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                    if node.field.metadata.get("editable", True):
                        flags |= Qt.ItemFlag.ItemIsEditable
                    return flags
            return Qt.ItemFlag.ItemIsEnabled

    def set_to_default(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        tree_item = index.internalPointer()
        assert isinstance(tree_item, PropertiesTreeItem)
        field = tree_item.field
        if field is None:
            return
        default_value = self.get_default_value(field)
        self.setData(index, default_value, Qt.ItemDataRole.EditRole)

    def has_default(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False
        tree_item = index.internalPointer()
        assert isinstance(tree_item, PropertiesTreeItem)
        field = tree_item.field
        if field is None:
            return False
        return hasattr(field, "default")

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 2

    def index(
        self, row: int, column: int, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        if not parent.isValid():
            parent_item = self._root_node
        else:
            parent_item = parent.internalPointer()
        assert isinstance(parent_item, PropertiesTreeItem)
        child_item = parent_item.child(row)

        if child_item:
            return self.createIndex(row, column, child_item)
        else:
            return QModelIndex()


class GRPCPropertiesModel(PropertiesModel):
    def __init__(self, client: Client, parent=None):
        super().__init__(EmptyDataclass(), parent)

        self._client = client
        self._stream_reader = None
        self._object_id = None

    def set_object(self, object_id: str):
        self._object_id = object_id

        self._fetch_initial_state()

        if self._stream_reader:
            self._stream_reader.stop()

        if self._object_id is not None:
            self._stream_reader = StreamReader(
                stream=self._client.object_stub.ListenPropertiesChanges(
                    ObjectId(id=self._object_id)
                ),
                on_data=self._handle_properties_changes,
            )
        else:
            self._stream_reader = None

    def _fetch_initial_state(self) -> bool:
        if self._object_id is None:
            self.set_dataclass_instance(EmptyDataclass())
            return False

        try:
            response = self._client.object_stub.GetProperties(
                ObjectId(id=self._object_id)
            )
        except Exception:
            self.set_dataclass_instance(EmptyDataclass())
            return False

        fields = []
        values = {}

        for prop in response.properties:
            base_path = prop.property_name
            base_value = convert_from_value(prop.value)
            editable = not prop.read_only

            if base_value is None:
                continue

            prop_fields, prop_values = flatten_dict_field(
                base_value,
                base_path,
                field_prefix=base_path,
                editable=editable,
            )
            fields.extend(prop_fields)
            values.update(prop_values)

        dataclass_instance = create_properties_dataclass(
            fields, values, self._change_property
        )
        self.set_dataclass_instance(dataclass_instance)
        return True

    def _change_property(
        self, field_name: str, old_value: typing.Any, new_value: typing.Any
    ):
        root_field = field_name.split("_", 1)[0]
        value_to_send = unflatten_dict_field(
            self.get_dataclass(), root_field, [(field_name, new_value)]
        )

        self._client.object_stub.UpdateProperty(
            PropertyUpdate(
                object_id=ObjectId(id=self._object_id),
                property_name=root_field,
                value=convert_to_value(value_to_send),
            )
        )

    def _handle_properties_changes(self, change):
        if change.HasField("added"):
            QMetaObject.invokeMethod(
                self,
                "_handle_property_added",
                Qt.QueuedConnection,
                Q_ARG(str, change.added.property_name),
                Q_ARG("QVariant", change.added.value),
            )
        elif change.HasField("removed"):
            QMetaObject.invokeMethod(
                self,
                "_handle_property_removed",
                Qt.QueuedConnection,
                Q_ARG(str, change.removed.property_name),
            )
        elif change.HasField("updated"):
            QMetaObject.invokeMethod(
                self,
                "_handle_property_updated",
                Qt.QueuedConnection,
                Q_ARG(str, change.updated.property_name),
                Q_ARG("QVariant", change.updated.old_value),
                Q_ARG("QVariant", change.updated.new_value),
            )

    @Slot(str, "QVariant")
    def _handle_property_added(self, property, value):
        pass

    @Slot(str, "QVariant")
    def _handle_property_removed(self, property):
        pass

    @Slot(str, "QVariant", "QVariant")
    def _handle_property_updated(self, property, old_value, new_value):
        instance = self.get_dataclass()
        observed_dict: ObservableDict = getattr(instance, "__dict__")
        updated_value = convert_from_value(new_value)

        def flatten(prefix: str, value):
            result = {}
            if isinstance(value, dict):
                for k, v in value.items():
                    nested = flatten(f"{prefix}_{k}" if prefix else k, v)
                    result.update(nested)
            else:
                result[prefix] = value
            return result

        flat_updates = flatten(property, updated_value)

        for k, v in flat_updates.items():
            if k in observed_dict:
                index = self._find_index(k)
                observed_dict._super_setitem(k, v)
                self.dataChanged.emit(
                    self.index(index.row(), 0, index.parent()),
                    self.index(index.row(), 1, index.parent()),
                )

    def _find_index(
        self, property_name: str, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex | None:
        for row in range(self.rowCount(parent)):
            index = self.index(row, 0, parent)
            if not index.isValid():
                continue

            field = index.data(PropertiesModel.CustomDataRoles.FieldRole)
            if field is not None:
                if field.name == property_name:
                    return index

            child_index = self._find_index(property_name, parent=index)
            if child_index is not None:
                return child_index

        return None


class FilteredPropertiesTypeProxyModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        source_model = self.sourceModel()
        index = source_model.index(source_row, 0, source_parent)
        if not index.isValid():
            return True

        field_name = index.data(PropertiesModel.CustomDataRoles.AttributeNameRole)
        return not (isinstance(field_name, str) and field_name.endswith("type"))
