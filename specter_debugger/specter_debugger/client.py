import grpc
import threading

from specter_debugger.proto import specter_pb2 as pb2
from specter_debugger.proto import specter_pb2_grpc as pb2_grpc
from google.protobuf.empty_pb2 import Empty


class DebuggerClient:
    def __init__(self, address):
        self.channel = grpc.insecure_channel(address)
        self.stub = pb2_grpc.DebuggerServiceStub(self.channel)
        self._stop_event = threading.Event()

    def create_session(self):
        return self.stub.CreateSession(Empty())

    def list_sessions(self):
        return self.stub.ListSessions(Empty())

    def set_source(self, session_id, filename, data_bytes):
        request = pb2.SourceSet(
            session=pb2.Session(id=session_id), filename=filename, data=data_bytes
        )
        return self.stub.SetSource(request)

    def start(self, session_id):
        return self.stub.Start(pb2.Session(id=session_id))

    def resume(self, session_id):
        return self.stub.Resume(pb2.Session(id=session_id))

    def pause(self, session_id):
        return self.stub.Pause(pb2.Session(id=session_id))

    def stop(self, session_id):
        return self.stub.Stop(pb2.Session(id=session_id))

    def add_breakpoint(self, session_id, filename, lineno):
        request = pb2.BreakpointAdd(
            session=pb2.Session(id=session_id),
            breakpoint=pb2.Breakpoint(filename=filename, lineno=lineno),
        )
        return self.stub.AddBreakpoint(request)

    def remove_breakpoint(self, session_id, filename, lineno):
        request = pb2.BreakpointRemove(
            session=pb2.Session(id=session_id),
            breakpoint=pb2.Breakpoint(filename=filename, lineno=lineno),
        )
        return self.stub.RemoveBreakpoint(request)

    def get_breakpoints(self, session_id):
        return self.stub.GetBreakpoints(pb2.Session(id=session_id))

    def listen_events(self, session_id, callback):
        def _listen():
            try:
                request = pb2.Session(id=session_id)
                for event in self.stub.ListenEvents(request):
                    if self._stop_event.is_set():
                        break
                    callback(event)
            except grpc.RpcError:
                pass

        self._stop_event.clear()
        self._listener_thread = threading.Thread(target=_listen, daemon=True)
        self._listener_thread.start()

    def stop_listening(self):
        self._stop_event.set()
        if hasattr(self, "_listener_thread"):
            self._listener_thread.join(timeout=2)

    def close(self):
        self.stop_listening()
        self.channel.close()
