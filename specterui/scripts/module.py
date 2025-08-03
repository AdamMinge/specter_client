import time

from specterui.proto.specter_pb2 import ObjectQuery

from specterui.client import Client
from specterui.scripts.wrappers import ObjectWrapper


class Module:
    def __init__(self, client: Client):
        super().__init__()
        self._client = client

    def waitForObject(self, object_query, timeout=10):
        object_pb_request = ObjectQuery(query=object_query)

        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.object_service_stub.Find(object_pb_request)
            if response.objects:
                found_object_pb = response.objects[0]
                wrapper_class = ObjectWrapper.get_wrapper_class_for_query(
                    found_object_pb.query
                )
                return wrapper_class(self.object_service_stub, found_object_pb)
            time.sleep(0.5)

        raise TimeoutError(
            f"Object matching query '{object_query}' not found within {timeout} seconds."
        )
