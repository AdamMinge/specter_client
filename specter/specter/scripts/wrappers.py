import json
import typing

from specter.proto.specter_pb2 import ObjectId, MethodCall, PropertyUpdate

from specter.client import convert_from_value, convert_to_value


class ObjectWrapper:
    _type_registry = {}

    def __init__(self, object_stub, object_id: str, object_query: str):
        self._stub = object_stub
        self._object_id: str = object_id
        self._object_query: str = object_query
        self._methods_cache: dict = None
        self._properties_cache: dict = None

    @property
    def id(self) -> str:
        return self._object_id

    @property
    def query(self) -> str:
        return self._object_query

    def _get_methods(self):
        if self._methods_cache is None:
            response = self._stub.GetMethods(ObjectId(id=self._object_id))
            self._methods_cache = {m.method_name: m for m in response.methods}
        return self._methods_cache

    def _get_properties(self):
        if self._properties_cache is None:
            response = self._stub.GetProperties(ObjectId(id=self._object_id))
            self._properties_cache = {p.property_name: p for p in response.properties}
        return self._properties_cache

    def _call_remote_method(self, method_name: str, *args):
        method_info = self._get_methods().get(method_name)
        if not method_info:
            raise AttributeError(
                f"Method '{method_name}' not found on object with query: {self.query}"
            )

        pb_args = [convert_to_value(arg) for arg in args]
        method_call_pb = MethodCall(
            object_id=ObjectId(id=self._object_id),
            method_name=method_name,
            arguments=pb_args,
        )
        self._stub.CallMethod(method_call_pb)

    def _get_remote_property(self, property_name: str):
        properties = self._get_properties()
        prop_pb = properties.get(property_name)
        if not prop_pb:
            self._properties_cache = None
            properties = self._get_properties()
            prop_pb = properties.get(property_name)
            if not prop_pb:
                raise AttributeError(
                    f"Property '{property_name}' not found on object with query: {self.query}"
                )
        return convert_from_value(prop_pb.value)

    def _set_remote_property(self, property_name: str, value: typing.Any):
        properties = self._get_properties()
        prop_pb = properties.get(property_name)
        if not prop_pb:
            self._properties_cache = None
            properties = self._get_properties()
            prop_pb = properties.get(property_name)
            if not prop_pb:
                raise AttributeError(
                    f"Property '{property_name}' not found on object with query: {self.query}"
                )
        if prop_pb.read_only:
            raise AttributeError(
                f"Property '{property_name}' is read-only on object with query: {self.query}"
            )

        pb_value = convert_to_value(value)
        property_update_pb = PropertyUpdate(
            object_id=ObjectId(id=self._object_id),
            property_name=property_name,
            value=pb_value,
        )

        self._stub.UpdateProperty(property_update_pb)
        self._properties_cache = None

    def getChildren(self):
        response = self._stub.GetChildren(ObjectId(id=self._object_id))
        children = []
        for obj_pb in response.ids:
            children.append(ObjectWrapper.create_wrapper_object(self._stub, obj_pb.id))
        return children

    def getParent(self):
        parent_pb = self._stub.GetParent(ObjectId(id=self._object_id))
        if parent_pb and parent_pb.id:
            return ObjectWrapper.create_wrapper_object(self._stub, parent_pb.id)
        return None

    def __getattr__(self, name: str):
        if name in self._get_methods():

            def remote_method_caller(*args):
                return self._call_remote_method(name, *args)

            return remote_method_caller
        elif name in self._get_properties():
            return self._get_remote_property(name)
        else:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}' "
                f"and no remote method or property named '{name}' for object {self.query}"
            )

    def __setattr__(self, name: str, value: typing.Any):
        if name.startswith("_") or name in ["query"]:
            super().__setattr__(name, value)
        elif name in self._get_properties():
            self._set_remote_property(name, value)
        else:
            super().__setattr__(name, value)

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.id} query='{self.query}'>"

    @classmethod
    def register_type(cls, type_name: str):
        def decorator(wrapper_class):
            cls._type_registry[type_name.lower()] = wrapper_class
            return wrapper_class

        return decorator

    @classmethod
    def get_wrapper_class(cls, query: str):
        obj_type = "qobject"
        try:
            query_dict = json.loads(query)
            obj_type = query_dict.get("type", "qobject").lower()
        except json.JSONDecodeError:
            pass
        return cls._type_registry.get(obj_type, QObjectWrapper)

    @classmethod
    def create_wrapper_object(cls, object_stub, object_id: str):
        query_pb = object_stub.GetObjectQuery(ObjectId(id=object_id))
        object_query = query_pb.query

        wrapper_class = cls.get_wrapper_class(object_query)
        return wrapper_class(object_stub, object_id, object_query)


@ObjectWrapper.register_type("qobject")
class QObjectWrapper(ObjectWrapper):
    pass


@ObjectWrapper.register_type("qwidget")
class QWidgetWrapper(QObjectWrapper):
    def setGeometry(self, x, y, width, height):
        self._call_remote_method("setGeometry", x, y, width, height)

    def isVisible(self):
        return self._get_remote_property("visible")


@ObjectWrapper.register_type("qwindow")
class QWindowWrapper(QWidgetWrapper):
    def setPos(self, x, y):
        self._call_remote_method("setPosition", x, y)

    @property
    def title(self):
        return self._get_remote_property("title")

    @title.setter
    def title(self, value):
        self._set_remote_property("title", value)


@ObjectWrapper.register_type("qlineedit")
class QLineEditWrapper(QWidgetWrapper):
    def setText(self, text):
        self.text = text

    def text(self):
        return self._get_remote_property("text")

    def clear(self):
        self._call_remote_method("clear")


@ObjectWrapper.register_type("qpushbutton")
class QPushButtonWrapper(QWidgetWrapper):
    def click(self):
        self._call_remote_method("click")
