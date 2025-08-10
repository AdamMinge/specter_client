import concurrent
import threading
import linecache
import queue
import uuid
import grpc
import time
import bdb
import sys
import os

from specter_debugger.proto import specter_pb2 as pb2
from specter_debugger.proto import specter_pb2_grpc as pb2_grpc
from google.protobuf.empty_pb2 import Empty


class OutputCapture:
    def __init__(self, queue, event_type):
        self.queue = queue
        self.event_type = event_type
        self._buffer = []

    def write(self, text):
        if text:
            self._buffer.append(text)
            if "\n" in text:
                self.flush()

    def flush(self):
        if self._buffer:
            message = "".join(self._buffer)
            self._buffer.clear()
            event = pb2.Event()
            if self.event_type == "stdout":
                event.stdout_event.message = message
            else:
                event.stderr_event.message = message
            self.queue.put(event)

    def isatty(self):
        return False


class DebuggerSession:
    def __init__(self, session_id):
        self.id = session_id
        self.filename = None
        self.data = None
        self.breakpoints = []
        self.output_queue = queue.Queue()
        self.event_queue = queue.Queue()
        self.debugger: bdb.Bdb = self._create_debugger()
        self.thread = None
        self.running = False

    def _create_debugger(self):
        session = self

        class ServerBdb(bdb.Bdb):
            def user_line(self_inner, frame):
                filename = frame.f_code.co_filename
                if filename == self.filename:
                    lineno = frame.f_lineno
                    ev = pb2.Event(
                        line_changed_event=pb2.LineChangedEvent(
                            filename=filename, lineno=lineno
                        )
                    )
                    session.event_queue.put(ev)

            def user_exception(self_inner, frame, exc_info):
                filename = frame.f_code.co_filename
                current_file = os.path.abspath(filename)
                if current_file == self.filename:
                    exc_type, exc_value, _ = exc_info
                    msg = f"Exception: {exc_type.__name__}: {exc_value}"
                    session.event_queue.put(
                        pb2.Event(stderr_event=pb2.StderrEvent(message=msg))
                    )

            def user_return(self_inner, frame, value):
                pass

            def user_call(self_inner, frame, argument_list):
                pass

            def interaction(self_inner, frame, traceback):
                pass

        return ServerBdb()

    def run_debugger(self):
        if self.running:
            return

        self.running = True

        status = "success"
        try:
            if not self.data:
                self.event_queue.put(
                    pb2.Event(
                        stderr_event=pb2.StderrEvent(
                            message="No source set for session"
                        )
                    )
                )
                status = "error: no source set"
                return

            code = self.data.decode("utf-8")

            linecache.cache[self.filename] = (
                len(code),
                None,
                code.splitlines(True),
                self.filename,
            )

            code_obj = compile(code, self.filename, "exec")

            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = OutputCapture(self.event_queue, "stdout")
            sys.stderr = OutputCapture(self.event_queue, "stderr")

            self.event_queue.put(pb2.Event(started_event=pb2.StartedEvent()))

            try:
                self.debugger.runctx(code_obj, globals(), locals())
            finally:
                sys.stdout.flush()
                sys.stderr.flush()

                sys.stdout = original_stdout
                sys.stderr = original_stderr

        except Exception as e:
            self.event_queue.put(
                pb2.Event(stderr_event=pb2.StderrEvent(message=f"Exception: {e}"))
            )
            status = f"error: {e}"
        finally:
            self.event_queue.put(
                pb2.Event(finished_event=pb2.FinishedEvent(status=status))
            )
            self.running = False

            if self.filename in linecache.cache:
                del linecache.cache[self.filename]


class DebuggerService(pb2_grpc.DebuggerServiceServicer):
    def __init__(self):
        self.sessions = {}
        self.sessions_lock = threading.Lock()

    def CreateSession(self, request, context):
        session_id = str(uuid.uuid4())
        session = DebuggerSession(session_id)
        with self.sessions_lock:
            self.sessions[session_id] = session
        return pb2.Session(id=session_id)

    def ListSessions(self, request, context):
        with self.sessions_lock:
            sessions = [pb2.Session(id=sid) for sid in self.sessions.keys()]
        return pb2.Sessions(sessions=sessions)

    def SetSource(self, request, context):
        session = self._get_session(request.session.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        session.data = request.data
        session.filename = request.filename
        return Empty()

    def Start(self, request, context):
        session = self._get_session(request.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        if session.thread and session.thread.is_alive():
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION, "Session already running"
            )

        session.thread = threading.Thread(target=session.run_debugger, daemon=True)
        session.thread.start()

        return Empty()

    def Pause(self, request, context):
        # Pause is unimplemented in this basic example
        return Empty()

    def Stop(self, request, context):
        session = self._get_session(request.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        # Stopping forcibly is unsafe; set running = False to indicate stop
        session.running = False
        return Empty()

    def AddBreakpoint(self, request, context):
        session = self._get_session(request.session.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        bp = request.breakpoint
        if (err := session.debugger.set_break(bp.filename, bp.lineno)) is not None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Cannot add breakpoint: {err}")

        session.breakpoints.append(bp)
        return Empty()

    def RemoveBreakpoint(self, request, context):
        session = self._get_session(request.session.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        bp = request.breakpoint
        if (err := session.debugger.clear_break(bp.filename, bp.lineno)) is not None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Cannot add breakpoint: {err}")

        session.breakpoints = [
            b
            for b in session.breakpoints
            if not (b.filename == bp.filename and b.lineno == bp.lineno)
        ]
        return Empty()

    def GetBreakpoints(self, request, context):
        session = self._get_session(request.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        return pb2.Breakpoints(breakpoints=session.breakpoints)

    def ListenEvents(self, request, context):
        session = self._get_session(request.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        while True:
            try:
                event = session.event_queue.get(timeout=1)
                yield event
            except queue.Empty:
                if context.is_active():
                    continue
                else:
                    break

    def _get_session(self, session_id):
        with self.sessions_lock:
            return self.sessions.get(session_id, None)


class DebuggerServer:
    def __init__(self, address):
        self._address = address
        self._server = grpc.server(
            concurrent.futures.ThreadPoolExecutor(max_workers=10)
        )
        pb2_grpc.add_DebuggerServiceServicer_to_server(DebuggerService(), self._server)
        self._server.add_insecure_port(address)
        self._stop_event = threading.Event()
        self._server_thread = None

    def start(self):
        self._server.start()
        self._stop_event.clear()

        def _serve():
            try:
                while not self._stop_event.is_set():
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

        self._server_thread = threading.Thread(target=_serve, daemon=True)
        self._server_thread.start()

    def stop(self):
        self._stop_event.set()
        self._server.stop(0)
        if self._server_thread:
            self._server_thread.join()
