import pyinjector
import subprocess
import typing
import psutil
import time
import os

from PySide6.QtNetwork import QHostAddress

from specterui.client import Client


CONNECTING_TIMEOUT = 5
ATTACHING_TIMEOUT = 5


class AttachException(Exception):
    def __init__(self, error_str: str):
        self._error_str = error_str

    def __str__(self):
        return self._error_str


def _find_subprocess(pid: int, subprocess_name: str) -> typing.Optional[int]:
    main_process = psutil.Process(pid)

    matching_subprocess = None
    for child in main_process.children(recursive=True):
        if child.name() == subprocess_name:
            matching_subprocess = child
            break

    if matching_subprocess:
        return matching_subprocess.pid

    return None


def _wait_for_process(pid: int, timeout: int) -> tuple[bool, int]:
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            process = psutil.Process(pid)
            if process.is_running():
                return (True, pid)
        except psutil.NoSuchProcess:
            time.sleep(0.1)
    return (False, 0)


def _wait_for_subprocess(
    pid: int, subprocess_name: str, timeout: int
) -> tuple[bool, int]:
    start_time = time.time()
    while time.time() - start_time < timeout:
        child_pid = _find_subprocess(pid, subprocess_name)
        if child_pid:
            return (True, child_pid)
        time.sleep(0.1)
    return (False, 0)


def attach_to_existing_process(
    host: QHostAddress, port: int, pid: int, library: str
) -> Client:
    try:
        pyinjector.inject(pid, library)
    except pyinjector.InjectorError as e:
        raise AttachException(str(e))

    client = Client()
    client.connect_to_host(host, port)
    if not client.wait_for_connected(CONNECTING_TIMEOUT):
        raise AttachException(
            f"Connection failed to {host.toString()}:{port} after waiting for {CONNECTING_TIMEOUT} ms"
        )

    return client


def attach_to_new_process(
    host: QHostAddress,
    port: int,
    app: str,
    library: str,
    subprocess_name: typing.Optional[str] = None,
) -> Client:

    app_full_path = os.path.abspath(app)
    app_directory = os.path.dirname(app_full_path)

    try:
        process = subprocess.Popen([app], env=os.environ, cwd=app_directory)
        time.sleep(0.5)
    except OSError as e:
        raise AttachException(str(e))

    pid = process.pid
    if subprocess_name:
        found, pid = _wait_for_subprocess(pid, subprocess_name, ATTACHING_TIMEOUT)
        if not found:
            raise AttachException(
                f"Subprocess with name '{subprocess_name}' not found after waiting for {ATTACHING_TIMEOUT} seconds"
            )
    else:
        found, pid = _wait_for_process(pid, ATTACHING_TIMEOUT)
        if not found:
            raise AttachException(
                f"Process {pid} not available after waiting for {ATTACHING_TIMEOUT} seconds"
            )

    return attach_to_existing_process(host, port, pid, library)
