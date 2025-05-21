import os

from PySide6.QtNetwork import QHostAddress

SPECTERUI_SERVER_HOST = QHostAddress(os.environ.get("SPECTERUI_SERVER_HOST", "127.0.0.1"))
SPECTERUI_SERVER_PORT = int(os.environ.get("SPECTERUI_SERVER_HOST", "5010"))
SPECTERUI_SERVER_DLL = str(os.environ.get("SPECTERUI_SERVER_DLL"))
