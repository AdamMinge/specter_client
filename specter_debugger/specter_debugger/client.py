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

    def create_session_from_file(self, filepath):
        request = pb2.SessionCreate(
            session_create_from_file=pb2.SessionCreateFromFile(file=filepath)
        )
        return self.stub.CreateSession(request)

    def create_session_from_data(self, data_bytes):
        request = pb2.SessionCreate(
            session_create_from_data=pb2.SessionCreateFromData(data=data_bytes)
        )
        return self.stub.CreateSession(request)

    def list_sessions(self):
        return self.stub.ListSessions(Empty())

    def start(self, session_id):
        request = pb2.Session(id=session_id)
        return self.stub.Start(request)

    def pause(self, session_id):
        request = pb2.Session(id=session_id)
        return self.stub.Pause(request)

    def stop(self, session_id):
        request = pb2.Session(id=session_id)
        return self.stub.Stop(request)

    def set_breakpoints(self, session_id, breakpoints):
        bp_messages = [pb2.Breakpoint(filename=fn, lineno=ln) for fn, ln in breakpoints]
        request = pb2.BreakpointsSet(
            session=pb2.Session(id=session_id),
            breakpoints=pb2.Breakpoints(breakpoints=bp_messages),
        )
        return self.stub.SetBreakpoint(request)

    def get_breakpoints(self, session_id):
        request = pb2.Session(id=session_id)
        return self.stub.GetBreakpoints(request)

    def listen_events(self, session_id, callback):
        def _listen():
            try:
                request = pb2.Session(id=session_id)
                for event in self.stub.ListenEvents(request):
                    if self._stop_event.is_set():
                        break
                    callback(event)
            except grpc.RpcError as e:
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
