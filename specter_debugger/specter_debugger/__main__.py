import argparse

from specter_debugger.cli import DebuggerClientCLI, DebuggerServerCLI
from specter_debugger.constants import (
    SPECTER_DEBUGGER_SERVER_HOST,
    SPECTER_DEBUGGER_SERVER_PORT,
)


def create_server_parser(subparsers) -> argparse.ArgumentParser:
    server_parser = subparsers.add_parser(
        "server", help="Start a debug server for a target script"
    )
    server_parser.add_argument(
        "--host",
        default=SPECTER_DEBUGGER_SERVER_HOST,
        help=f"Host for server (default {SPECTER_DEBUGGER_SERVER_HOST})",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=SPECTER_DEBUGGER_SERVER_PORT,
        help=f"Port for server (default {SPECTER_DEBUGGER_SERVER_PORT})",
    )

    return server_parser


def create_client_parser(subparsers) -> argparse.ArgumentParser:
    client_parser = subparsers.add_parser(
        "client", help="Connect to a debug server as a client"
    )
    client_parser.add_argument(
        "--host",
        default=SPECTER_DEBUGGER_SERVER_HOST,
        help=f"Host of server to connect to (default {SPECTER_DEBUGGER_SERVER_HOST})",
    )
    client_parser.add_argument(
        "--port",
        type=int,
        default=SPECTER_DEBUGGER_SERVER_PORT,
        help=f"Port of server to connect to (default {SPECTER_DEBUGGER_SERVER_PORT})",
    )

    return client_parser


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Specter Debugger in server or client mode"
    )

    subparsers = parser.add_subparsers(dest="mode", required=True)
    create_server_parser(subparsers)
    create_client_parser(subparsers)

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    address = f"{args.host}:{args.port}"

    if args.mode == "server":
        cli = DebuggerServerCLI(address)
        cli.run()

    elif args.mode == "client":
        client = DebuggerClientCLI(address)
        client.run()


if __name__ == "__main__":
    main()
