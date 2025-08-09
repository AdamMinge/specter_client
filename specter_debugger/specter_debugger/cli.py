from specter_debugger.client import DebuggerClient
from specter_debugger.server import DebuggerServer


class DebuggerClientCLI:
    def __init__(self, address="localhost:50051"):
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
            elif command == "create_file":
                if len(args) != 2:
                    print("Usage: create_file <filename>")
                    continue
                self.session_id = self.create_session_from_file(args[1])
            elif command == "create_data":
                if len(args) != 2:
                    print("Usage: create_data <filepath>")
                    continue
                self.session_id = self.create_session_from_data(args[1])
            elif command == "list":
                self.list_sessions()
            elif command == "start":
                self.start()
            elif command == "stop":
                self.stop()
            elif command == "set_breakpoints":
                if len(args) < 2:
                    print(
                        "Usage: set_breakpoints <filename:lineno> [<filename:lineno> ...]"
                    )
                    continue
                self.set_breakpoints(args[1:])
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
            """
Commands:
  create_file <filename>      - Create debugging session from source file
  create_data <filepath>      - Create debugging session from file bytes
  list                        - List active sessions
  start                       - Start debugging current session
  stop                        - Stop debugging current session
  set_breakpoints f:ln [...]  - Set breakpoints, example: foo.py:10 bar.py:20
  get_breakpoints             - Get breakpoints of current session
  listen                      - Start listening to debug events (async)
  stop_listen                 - Stop listening to events
  exit                        - Exit CLI
"""
        )

    def create_session_from_file(self, filepath):
        try:
            session = self.client.create_session_from_file(filepath)
            print(f"Session created with id: {session.id}")
            return session.id
        except Exception as e:
            print(f"Error creating session: {e}")

    def create_session_from_data(self, filepath):
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            session = self.client.create_session_from_data(data)
            print(f"Session created with id: {session.id}")
            return session.id
        except Exception as e:
            print(f"Error creating session: {e}")

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

    def set_breakpoints(self, bp_args):
        if not self.session_id:
            print("No session selected")
            return
        try:
            breakpoints = []
            for bp_str in bp_args:
                if ":" not in bp_str:
                    print(
                        f"Invalid breakpoint format: {bp_str}, expected filename:lineno"
                    )
                    return
                filename, lineno_str = bp_str.split(":", 1)
                lineno = int(lineno_str)
                breakpoints.append((filename, lineno))
            self.client.set_breakpoints(self.session_id, breakpoints)
            print(f"Set {len(breakpoints)} breakpoints")
        except Exception as e:
            print(f"Error setting breakpoints: {e}")

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
            elif event.HasField("debug_session_finished_event"):
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
    def __init__(self, address):
        self.server = DebuggerServer(address)
        self.running = False

    def run(self):
        print("Specter Debugger Server CLI")
        print("Type 'help' for commands")

        while True:
            try:
                cmd = input("> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting...")
                if self.running:
                    self.server.stop()
                break

            if not cmd:
                continue

            command = cmd.lower()

            if command == "help":
                self.print_help()
            elif command == "start":
                if self.running:
                    print("Server is already running.")
                else:
                    self.server.start()
                    self.running = True
            elif command == "stop":
                if not self.running:
                    print("Server is not running.")
                else:
                    self.server.stop()
                    self.running = False
            elif command == "exit":
                if self.running:
                    self.server.stop()
                print("Goodbye!")
                break
            else:
                print(f"Unknown command: {command}")

    def print_help(self):
        print(
            """
Commands:
  start  - Start the gRPC debugger server
  stop   - Stop the gRPC debugger server
  exit   - Exit this CLI
  help   - Show this help message
"""
        )
