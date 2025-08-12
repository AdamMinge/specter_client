import time

from specter.proto.specter_pb2 import ObjectSearchQuery

from specter.client import Client
from specter.scripts.wrappers import ObjectWrapper


class ScriptModule:
    def __init__(self, client: Client):
        super().__init__()
        self._client = client

    def waitForObject(self, object_query, timeout=10):
        object_pb_request = ObjectSearchQuery(query=object_query)

        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self._client.object_stub.Find(object_pb_request)

            if len(response.ids) == 1:
                found_object_pb = response.ids[0]
                return ObjectWrapper.create_wrapper_object(
                    self._client.object_stub, found_object_pb.id
                )
            time.sleep(0.5)

        raise TimeoutError(
            f"Object matching query '{object_query}' not found within {timeout} seconds."
        )
