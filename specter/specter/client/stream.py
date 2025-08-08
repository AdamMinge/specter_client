import threading
import grpc

class StreamReader:
    def __init__(self, stream, on_data=None, on_error=None):
        self._iter = iter(stream)
        self._stream = stream
        self._on_data = on_data
        self._on_error = on_error
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self.__run, daemon=True)
        self._thread.start()

    def __del__(self):
        self.stop()

    def __run(self):
        try:
            while not self._stop_event.is_set():
                try:
                    response = next(self._iter)
                    if self._on_data:
                        self._on_data(response)
                except grpc.RpcError as e:
                    if not self._stop_event.is_set() and self._on_error:
                        self._on_error(e)
                    break
        except Exception as e:
            if self._on_error:
                self._on_error(e)

    def stop(self):
        self._stop_event.set()
        try:
            self._stream.cancel()
        except Exception:
            pass
        self._thread.join()