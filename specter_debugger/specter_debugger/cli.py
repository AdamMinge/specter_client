from specter_debugger.client import DebuggerClient
from specter_debugger.server import DebuggerServer


class DebuggerClientCLI:
    def __init__(self, address: str = "localhost:50051"):
        self.client = DebuggerClient(address)
        self.session_id = None
        self.listening = False

    def run(self):
        print("Specter Debugger Client CLI")
        print("Type 'help' for commands")
        while True:
            try:
                cmd = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                break

            if not cmd:
                continue
            args = cmd.split()
            command = args[0].lower()

            if command == "help":
                self.print_help()
            elif command == "exit":
                break
            elif command == "create_session":
                self.session_id = self.create_session()
            elif command == "get_sessions":
                self.list_sessions()
            elif command == "set_source":
                if len(args) != 2:
                    print("Usage: set_source <filename>")
                    continue
                self.set_source(args[1])
            elif command == "start":
                self.start()
            elif command == "stop":
                self.stop()
            elif command == "add_breakpoint":
                if len(args) != 2:
                    print("Usage: add_breakpoint <filename:lineno>")
                    continue
                self.add_breakpoint(args[1])
            elif command == "remove_breakpoint":
                if len(args) != 2:
                    print("Usage: remove_breakpoint <filename:lineno>")
                    continue
                self.remove_breakpoint(args[1])
            elif command == "get_breakpoints":
                self.get_breakpoints()
            elif command == "listen":
                self.listen_events()
            elif command == "stop_listen":
                self.stop_listening()
            else:
                print(f"Unknown command: {command}")

        self.client.close()

    def print_help(self):
        print(
            "Commands: \n",
            "create_session            - Create debugging session \n",
            "get_sessions              - List active sessions \n",
            "set_source <filename>     - Set source for current session \n",
            "start                     - Start debugging current session \n",
            "stop                      - Stop debugging current session \n",
            "add_breakpoint f:ln       - Add a breakpoint, example: foo.py:10 \n",
            "remove_breakpoint f:ln    - Remove a breakpoint, example: foo.py:10 \n",
            "get_breakpoints           - Get breakpoints of current session \n",
            "listen                    - Start listening to debug events (async) \n",
            "stop_listen               - Stop listening to events \n",
            "exit                      - Exit CLI \n",
        )

    def create_session(self):
        try:
            session = self.client.create_session()
            print(f"Session created with id: {session.id}")
            return session.id
        except Exception as e:
            print(f"Error creating session: {e}")

    def set_source(self, filepath):
        if not self.session_id:
            print("No session selected")
            return
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.client.set_source(self.session_id, data)
            print(f"Source set from {filepath}")
        except Exception as e:
            print(f"Error setting source: {e}")

    def list_sessions(self):
        try:
            sessions = self.client.list_sessions()
            if not sessions.sessions:
                print("No active sessions")
                return
            print("Active sessions:")
            for s in sessions.sessions:
                print(f"  - {s.id}")
        except Exception as e:
            print(f"Error listing sessions: {e}")

    def start(self):
        if not self.session_id:
            print("No session selected")
            return
        try:
            self.client.start(self.session_id)
            print("Started debugging session")
        except Exception as e:
            print(f"Error starting session: {e}")

    def stop(self):
        if not self.session_id:
            print("No session selected")
            return
        try:
            self.client.stop(self.session_id)
            print("Stopped debugging session")
        except Exception as e:
            print(f"Error stopping session: {e}")

    def add_breakpoint(self, bp_str):
        if not self.session_id:
            print("No session selected")
            return
        try:
            filename, lineno_str = bp_str.split(":", 1)
            lineno = int(lineno_str)
            self.client.add_breakpoint(self.session_id, filename, lineno)
            print(f"Added breakpoint at {filename}:{lineno}")
        except Exception as e:
            print(f"Error adding breakpoint: {e}")

    def remove_breakpoint(self, bp_str):
        if not self.session_id:
            print("No session selected")
            return
        try:
            filename, lineno_str = bp_str.split(":", 1)
            lineno = int(lineno_str)
            self.client.remove_breakpoint(self.session_id, filename, lineno)
            print(f"Removed breakpoint at {filename}:{lineno}")
        except Exception as e:
            print(f"Error removing breakpoint: {e}")

    def get_breakpoints(self):
        if not self.session_id:
            print("No session selected")
            return
        try:
            bps = self.client.get_breakpoints(self.session_id)
            if not bps.breakpoints:
                print("No breakpoints set")
                return
            print("Breakpoints:")
            for bp in bps.breakpoints:
                print(f"  - {bp.filename}:{bp.lineno}")
        except Exception as e:
            print(f"Error getting breakpoints: {e}")

    def listen_events(self):
        if not self.session_id:
            print("No session selected")
            return
        if self.listening:
            print("Already listening")
            return

        def on_event(event):
            if event.HasField("line_changed_event"):
                e = event.line_changed_event
                print(f"[EVENT] Line changed: {e.filename}:{e.lineno}")
            elif event.HasField("finished_event"):
                print("[EVENT] Debug session finished")
            elif event.HasField("stdout_event"):
                print(f"[STDOUT] {event.stdout_event.message}")
            elif event.HasField("stderr_event"):
                print(f"[STDERR] {event.stderr_event.message}")

        self.listening = True
        self.client.listen_events(self.session_id, on_event)
        print("Started listening to events")

    def stop_listening(self):
        if not self.listening:
            print("Not currently listening")
            return
        self.client.stop_listening()
        self.listening = False
        print("Stopped listening to events")


class DebuggerServerCLI:
    def __init__(self, address: str, autostart: bool):
        self._server = DebuggerServer(address)
        self._autostart = autostart
        self._running = False

    def run(self):
        print("Specter Debugger Server CLI")
        print("Type 'help' for commands")

        if self._autostart:
            self._start()

        while True:
            try:
                cmd = input("> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting...")
                if self._running:
                    self._server.stop()
                break

            if not cmd:
                continue

            command = cmd.lower()

            if command == "help":
                self._print_help()
            elif command == "start":
                self._start()
            elif command == "stop":
                self._stop()
            elif command == "exit":
                self._exit()
                break
            else:
                print(f"Unknown command: {command}")

    def _start(self):
        if self._running:
            print("Server is already running.")
        else:
            self._server.start()
            self._running = True

    def _stop(self):
        if not self._running:
            print("Server is not running.")
        else:
            self._server.stop()
            self._running = False

    def _exit(self):
        if self._running:
            self._server.stop()
        print("Goodbye!")

    def _print_help(self):
        print(
            "Commands: \n",
            "start  - Start the gRPC debugger server \n",
            "stop   - Stop the gRPC debugger server \n",
            "exit   - Exit this CLI \n",
            "help   - Show this help message \n",
        )
