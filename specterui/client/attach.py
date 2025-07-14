import pyinjector
import subprocess
import typing
import psutil
import time
import os

from PySide6.QtNetwork import QHostAddress

from specterui.client import Client


CONNECTING_TIMEOUT = 2.0
ATTACHING_TIMEOUT = 0.5


class AttachException(Exception):
    def __init__(self, error_str: str):
        self._error_str = error_str

    def __str__(self):
        return self._error_str


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


def attach_to_new_process(
    host: QHostAddress,
    port: int,
    app: str,
    library: str,
    subprocess_name: typing.Optional[str] = None,
) -> Client:
    try:
        process = subprocess.Popen([app], env=os.environ)
        time.sleep(ATTACHING_TIMEOUT)
    except OSError as e:
        raise AttachException(str(e))

    pid = process.pid
    if subprocess_name:
        child_pid = _find_subprocess(pid, subprocess_name)
        if not child_pid:
            raise AttachException(
                f"Subprocess with name '{subprocess_name}' not found."
            )
        pid = child_pid

    return attach_to_existing_process(host, port, pid, library)
