import concurrent
import threading
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
    def __init__(self, session_id, filename=None, data=None):
        self.id = session_id
        self.filename = filename
        self.data = data
        self.breakpoints = []
        self.output_queue = queue.Queue()
        self.event_queue = queue.Queue()
        self.debugger = self._create_debugger()
        self.thread = None
        self.running = False

    def _create_debugger(self):
        session = self
        target_file = self.filename or "<debugger_input>"

        class ServerBdb(bdb.Bdb):
            def user_line(self_inner, frame):
                filename = frame.f_code.co_filename
                if filename == target_file:
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
                if current_file == target_file:
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
        try:
            code = None

            if self.filename:
                with open(self.filename, "r") as f:
                    code = f.read()
            elif self.data:
                code = self.data.decode("utf-8")

            if code:
                filename_for_compilation = self.filename or "<debugger_input>"
                code_obj = compile(code, filename_for_compilation, "exec")

                original_stdout = sys.stdout
                original_stderr = sys.stderr
                sys.stdout = OutputCapture(self.event_queue, "stdout")
                sys.stderr = OutputCapture(self.event_queue, "stderr")

                try:
                    self.debugger.runctx(code_obj, globals(), locals())
                finally:
                    sys.stdout.flush()
                    sys.stderr.flush()

                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
            else:
                self.event_queue.put(
                    pb2.Event(stderr_event=pb2.StderrEvent(message="No code to run"))
                )
        except Exception as e:
            self.event_queue.put(
                pb2.Event(stderr_event=pb2.StderrEvent(message=f"Exception: {e}"))
            )
        finally:
            self.event_queue.put(
                pb2.Event(debug_session_finished_event=pb2.DebugSessionFinishedEvent())
            )
            self.running = False


class DebuggerService(pb2_grpc.DebuggerServiceServicer):
    def __init__(self):
        self.sessions = {}
        self.sessions_lock = threading.Lock()

    def CreateSession(self, request, context):
        session_id = str(uuid.uuid4())
        filename = None
        data = None

        if request.HasField("session_create_from_file"):
            filename = request.session_create_from_file.file
        elif request.HasField("session_create_from_data"):
            data = request.session_create_from_data.data

        session = DebuggerSession(session_id, filename=filename, data=data)

        with self.sessions_lock:
            self.sessions[session_id] = session

        return pb2.Session(id=session_id)

    def ListSessions(self, request, context):
        with self.sessions_lock:
            sessions = [pb2.Session(id=sid) for sid in self.sessions.keys()]
        return pb2.Sessions(sessions=sessions)

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

    def SetBreakpoint(self, request, context):
        session = self._get_session(request.session.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        session.debugger.clear_all_breaks()
        session.breakpoints.clear()

        for bp in request.breakpoints.breakpoints:
            session.debugger.set_break(bp.filename, bp.lineno)
            session.breakpoints.append(bp)

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
