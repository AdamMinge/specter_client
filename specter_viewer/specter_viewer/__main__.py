import sys
import logging
import argparse

from specter.client import attach_to_new_process, attach_to_existing_process

from specter_viewer import Application, AttachWizard, MainWindow, constants
from specter_viewer.resources import rcc


_formatter = logging.Formatter(
    fmt="[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
_handler_with_formatter = logging.StreamHandler(stream=sys.stdout)
_handler_with_formatter.setFormatter(_formatter)
logging.basicConfig(handlers=[_handler_with_formatter])


def attach_client(app: Application):
    parser = argparse.ArgumentParser(description="SpecterUI Process Attacher")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--pid", type=int, help="Attach to an existing process with the given PID"
    )
    group.add_argument(
        "--app", type=str, help="Path of the application to start and attach to"
    )

    args = parser.parse_args()
    if args.pid:
        return attach_to_existing_process(
            host=constants.SPECTER_VIEWER_SERVER_HOST,
            port=constants.SPECTER_VIEWER_SERVER_PORT,
            pid=args.pid,
            library=constants.SPECTER_VIEVER_SERVER_DLL,
        )
    elif args.app:
        return attach_to_new_process(
            host=constants.SPECTER_VIEWER_SERVER_HOST,
            port=constants.SPECTER_VIEWER_SERVER_PORT,
            app=args.app,
            library=constants.SPECTER_VIEVER_SERVER_DLL,
        )

    attach_wizard = AttachWizard()
    return attach_wizard.attach()


def main():
    app = Application(sys.argv)

    try:
        client = attach_client(app)
    except Exception as e:
        sys.exit(app.exit(1))
        return

    if not client:
        sys.exit(app.exit())
        return

    window = MainWindow(client)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
