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
        self._id = session_id
        self._filename = None
        self._code = None
        self._breakpoints = []
        self._output_queue = queue.Queue()
        self._event_queue = queue.Queue()
        self._debugger = self._create_debugger()
        self._thread = None
        self._running = False
        self._pause_event = threading.Event()
        self._pause_event.set()

    def _create_debugger(self):
        session = self

        class ServerBdb(bdb.Bdb):
            def user_line(self_inner, frame):
                filename = frame.f_code.co_filename
                lineno = frame.f_lineno

                if os.path.abspath(filename) == os.path.abspath(session._filename):
                    for bp_filename, bp_lineno in session._breakpoints:
                        if (
                            os.path.abspath(bp_filename) == os.path.abspath(filename)
                            and bp_lineno == lineno
                        ):
                            session.pause()
                            break

                    ev = pb2.Event(
                        line_changed_event=pb2.LineChangedEvent(
                            filename=filename, lineno=lineno
                        )
                    )
                    session._event_queue.put(ev)

                while session.is_paused():
                    time.sleep(0.1)

            def user_exception(self_inner, frame, exc_info):
                filename = frame.f_code.co_filename
                current_file = os.path.abspath(filename)
                if current_file == session._filename:
                    exc_type, exc_value, _ = exc_info
                    msg = f"Exception: {exc_type.__name__}: {exc_value}"
                    session._event_queue.put(
                        pb2.Event(stderr_event=pb2.StderrEvent(message=msg))
                    )

            def reset(self):
                filename_cache = linecache.cache.get(session._filename)
                super().reset()
                if filename_cache:
                    linecache.cache[session._filename] = filename_cache

        return ServerBdb()

    def _run_debugger(self):
        if self._running:
            return

        self._running = True

        status = "success"
        try:
            if self._code is None:
                self._event_queue.put(
                    pb2.Event(
                        stderr_event=pb2.StderrEvent(
                            message="No source set for session"
                        )
                    )
                )
                status = "error: no source set"
                return

            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = OutputCapture(self._event_queue, "stdout")
            sys.stderr = OutputCapture(self._event_queue, "stderr")

            try:
                compiled_code = compile(self._code, self._filename, "exec")
                self._debugger.runctx(compiled_code, globals(), locals())
            finally:
                sys.stdout.flush()
                sys.stderr.flush()

                sys.stdout = original_stdout
                sys.stderr = original_stderr

        except Exception as e:
            self._event_queue.put(
                pb2.Event(stderr_event=pb2.StderrEvent(message=f"Exception: {e}"))
            )
            status = f"error: {e}"
        finally:
            self._event_queue.put(
                pb2.Event(finished_event=pb2.FinishedEvent(status=status))
            )
            self._running = False

    def set_source(self, filename: str, source: bytes):
        code = source.decode("utf-8")

        self._filename = filename
        self._code = code

        linecache.cache[self._filename] = (
            len(code),
            None,
            code.splitlines(True),
            self._filename,
        )

    def start(self):
        self._thread = threading.Thread(target=self._run_debugger, daemon=True)
        self._event_queue.put(pb2.Event(started_event=pb2.StartedEvent()))
        self._thread.start()

    def pause(self):
        self._event_queue.put(pb2.Event(paused_event=pb2.PausedEvent()))
        self._pause_event.clear()

    def resume(self):
        self._event_queue.put(pb2.Event(resumed_event=pb2.ResumedEvent()))
        self._pause_event.set()

    def stop(self):
        self._debugger.set_quit()
        self._pause_event.set()
        self._running = False

    def is_running(self) -> bool:
        return self._thread and self._thread.is_alive()

    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def add_breakpoint(self, filename: str, lineno: int) -> bool:
        if self._debugger.set_break(filename, lineno) is not None:
            return False

        self._breakpoints.append((filename, lineno))
        return True

    def remove_breakpoint(self, filename: str, lineno: int) -> bool:
        if self._debugger.clear_break(filename, lineno) is not None:
            return False

        self._breakpoints = [
            (bp_filename, bp_lineno)
            for bp_filename, bp_lineno in self._breakpoints
            if not (bp_filename == filename and bp_lineno == lineno)
        ]

        return True

    def get_breakpoints(self):
        return self._breakpoints

    def get_event(self, timeout: int = 1):
        try:
            event = self._event_queue.get(timeout=timeout)
            return event
        except queue.Empty:
            return None


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

        session.set_source(request.filename, request.data)
        return Empty()

    def Start(self, request, context):
        session = self._get_session(request.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        if session.is_running():
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION, "Session already running"
            )

        session.start()
        return Empty()

    def Pause(self, request, context):
        session = self._get_session(request.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")
        if not session.is_running():
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Session not running")
        if session.is_paused():
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Session already paused")

        session.pause()
        return Empty()

    def Resume(self, request, context):
        session = self._get_session(request.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")
        if not session.is_running():
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Session not running")
        if not session.is_paused():
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Session not paused")

        session.resume()
        return Empty()

    def Stop(self, request, context):
        session = self._get_session(request.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")
        if not session.is_running():
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Session not running")

        session.stop()
        return Empty()

    def AddBreakpoint(self, request, context):
        session = self._get_session(request.session.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        bp = request.breakpoint
        if not session.add_breakpoint(bp.filename, bp.lineno):
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Cannot add breakpoint")

        return Empty()

    def RemoveBreakpoint(self, request, context):
        session = self._get_session(request.session.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        bp = request.breakpoint
        if not session.remove_breakpoint(bp.filename, bp.lineno):
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION, f"Cannot remove breakpoint"
            )

        return Empty()

    def GetBreakpoints(self, request, context):
        session = self._get_session(request.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        return pb2.Breakpoints(breakpoints=session.get_breakpoints())

    def ListenEvents(self, request, context):
        session = self._get_session(request.id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

        while True:
            if context.is_active():
                event = session.get_event(timeout=1)
                if event:
                    yield event
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
