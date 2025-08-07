import json

from specter.proto.specter_pb2 import MethodCall, PropertyUpdate

from specter.client import convert_from_value, convert_to_value


class ObjectWrapper:
    _type_registry = {}

    def __init__(self, object_service_stub, object_pb):
        self._stub = object_service_stub
        self._object_pb = object_pb
        self._query = object_pb.query
        self._methods_cache = None
        self._properties_cache = None

    @property
    def query(self):
        return self._query

    def _get_methods(self):
        if self._methods_cache is None:
            response = self._stub.GetMethods(self._object_pb)
            self._methods_cache = {m.name: m for m in response.methods}
        return self._methods_cache

    def _get_properties(self):
        if self._properties_cache is None:
            response = self._stub.GetProperties(self._object_pb)
            self._properties_cache = {p.name: p for p in response.properties}
        return self._properties_cache

    def _call_remote_method(self, method_name, *args):
        method_info = self._get_methods().get(method_name)
        if not method_info:
            raise AttributeError(
                f"Method '{method_name}' not found on object with query: {self.query}"
            )

        pb_args = [convert_to_value(arg) for arg in args]
        method_call_pb = MethodCall(
            object=self._object_pb, method=method_name, arguments=pb_args
        )
        self._stub.CallMethod(method_call_pb)

    def _get_remote_property(self, property_name):
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

    def _set_remote_property(self, property_name, value):
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
            object=self._object_pb, property=property_name, value=pb_value
        )
        self._stub.UpdateProperty(property_update_pb)
        self._properties_cache = None

    def getChildren(self):
        response = self._stub.GetChildren(self._object_pb)
        children = []
        for obj_pb in response.objects:
            child_wrapper_class = ObjectWrapper.get_wrapper_class_for_query(
                obj_pb.query
            )
            children.append(child_wrapper_class(self._stub, obj_pb))
        return children

    def getParent(self):
        parent_pb = self._stub.GetParent(self._object_pb)
        if parent_pb and parent_pb.query:
            parent_wrapper_class = ObjectWrapper.get_wrapper_class_for_query(
                parent_pb.query
            )
            return parent_wrapper_class(self._stub, parent_pb)
        return None

    def __getattr__(self, name):
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

    def __setattr__(self, name, value):
        if name.startswith("_") or name in ["query"]:
            super().__setattr__(name, value)
        elif name in self._get_properties():
            self._set_remote_property(name, value)
        else:
            super().__setattr__(name, value)

    def __repr__(self):
        return f"<{self.__class__.__name__} query='{self.query}'>"

    @classmethod
    def register_type(cls, type_name):
        def decorator(wrapper_class):
            cls._type_registry[type_name.lower()] = wrapper_class
            return wrapper_class

        return decorator

    @classmethod
    def get_wrapper_class_for_query(cls, query_json_string):
        obj_type = "qobject"
        try:
            query_dict = json.loads(query_json_string)
            obj_type = query_dict.get("type", "qobject").lower()
        except json.JSONDecodeError:
            pass
        return cls._type_registry.get(obj_type, QObjectWrapper)


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
