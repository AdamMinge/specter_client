import subprocess
import functools
import json

from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QTextEdit,
    QPlainTextEdit,
    QHBoxLayout,
    QVBoxLayout,
    QSizePolicy,
    QToolButton,
    QApplication,
)
from PySide6.QtCore import Qt, QObject, QSize, Signal, QRect, QFile, QIODevice
from PySide6.QtGui import (
    QSyntaxHighlighter,
    QTextCharFormat,
    QFont,
    QColor,
    QPainter,
    QTextFormat,
    QFontMetrics,
    QFontDatabase,
    QTextCursor,
    QPalette,
    QIcon,
    QPixmap,
    QPen,
    QKeyEvent,
)

from textmate import TextMateGrammarRepository, TextMateGrammar

from specter.client import Client
from specter_debugger import DebuggerClient

from specter_viewer.constants import (
    SPECTER_VIEVER_DEBUGGER_PATH,
    SPECTER_VIEVER_DEBUGGER_HOST,
    SPECTER_VIEVER_DEBUGGER_PORT,
)


def tx_format(color, style=""):
    _format = QTextCharFormat()

    if isinstance(color, str):
        _color = QColor()
        _color.setNamedColor(color)
        _format.setForeground(_color)
    else:
        _format.setForeground(color)

    if "bold" in style:
        _format.setFontWeight(QFont.Bold)
    if "italic" in style:
        _format.setFontItalic(True)

    return _format


STYLES_DARK = {
    "keyword": tx_format(QColor(86, 156, 214), "bold"),
    "defclass": tx_format(QColor(220, 220, 170), "bold"),
    "string": tx_format(QColor(206, 145, 120)),
    "comment": tx_format(QColor(106, 153, 85), "italic"),
    "numbers": tx_format(QColor(181, 206, 168)),
    "type": tx_format(QColor(78, 201, 176)),
    "typeparam": tx_format(QColor(156, 220, 254)),
    "fexpr": tx_format(QColor(220, 220, 170)),
}

STYLES_LIGHT = {
    "keyword": tx_format("blue", "bold"),
    "defclass": tx_format("darkMagenta", "bold"),
    "string": tx_format("brown"),
    "comment": tx_format("darkGreen", "italic"),
    "numbers": tx_format("darkRed"),
    "type": tx_format("teal"),
    "typeparam": tx_format("navy"),
    "fexpr": tx_format("black"),
}


def is_dark():
    app = QApplication.instance()
    if hasattr(app, "styleHints") and hasattr(app.styleHints(), "colorScheme"):
        return app.styleHints().colorScheme().value == 2
    return False


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.STYLES = STYLES_DARK if is_dark() else STYLES_LIGHT

        repository = self._load_repository()
        python_grammar_data = repository.get_grammar_by_language("python")
        self.grammar = TextMateGrammar(python_grammar_data, repository)

        self.scope_map = {
            "keyword": "keyword",
            "entity.name.function": "defclass",
            "entity.name.class": "defclass",
            "string": "string",
            "comment": "comment",
            "constant.numeric": "numbers",
            "support.type": "type",
            "variable.parameter": "typeparam",
            "meta.fstring": "fexpr",
        }

    def _load_repository(self):
        grammar_files = [
            ":/tm/MagicPython.tmLanguage.json",
        ]
        return TextMateGrammarRepository([self.load_json(f) for f in grammar_files])

    @staticmethod
    def load_json(filepath):
        file = QFile(filepath)
        if not file.open(QIODevice.ReadOnly | QIODevice.Text):
            raise FileNotFoundError(
                f"Resource {filepath} not found or cannot be opened"
            )
        data = file.readAll().data()
        file.close()
        return json.loads(data.decode("utf-8"))

    def highlightBlock(self, text):
        tokens = self.grammar.parse(text)

        for scope, (start, end) in tokens:
            for prefix, style_key in self.scope_map.items():
                if scope.startswith(prefix):
                    fmt = self.STYLES.get(style_key)
                    if fmt:
                        self.setFormat(start, end - start, fmt)
                    break


class LineNumberArea(QWidget):
    try_add_breakpoint = Signal(int)
    try_remove_breakpoint = Signal(int)

    _BREAKPOINT_COLOR = QColor(200, 0, 0)
    _BREAKPOINT_OUTLINE_COLOR = QColor(120, 0, 0)
    _BREAKPOINT_OUTLINE_WIDTH = 1.5
    _LINE_NUMBER_COLOR = QColor(100, 100, 100)
    _BACKGROUND_COLOR = QColor(240, 240, 240)
    _ICON_NUMBER_SPACING = 8

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

        self.breakpoints: set[int] = set()
        self.icon_margin: int = 5
        self.icon_radius: int = int(self.fontMetrics().height() / 3.5)
        self.number_right_margin: int = 5

    def sizeHint(self):
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), self._BACKGROUND_COLOR)

        block = self._editor.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(
            self._editor.blockBoundingGeometry(block)
            .translated(self._editor.contentOffset())
            .top()
        )
        bottom = top + int(self._editor.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                if blockNumber in self.breakpoints:
                    painter.setBrush(self._BREAKPOINT_COLOR)
                    painter.setPen(
                        QPen(
                            self._BREAKPOINT_OUTLINE_COLOR,
                            self._BREAKPOINT_OUTLINE_WIDTH,
                        )
                    )

                    center_x = self.icon_margin + self.icon_radius
                    center_y = top + self.fontMetrics().height() / 2

                    painter.drawEllipse(
                        int(center_x - self.icon_radius),
                        int(center_y - self.icon_radius),
                        int(self.icon_radius * 2),
                        int(self.icon_radius * 2),
                    )

                number = str(blockNumber + 1)
                painter.setPen(self._LINE_NUMBER_COLOR)

                text_width = self.fontMetrics().horizontalAdvance(number)
                painter.drawText(
                    self.width() - text_width - self.number_right_margin,
                    top,
                    text_width,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + int(self._editor.blockBoundingRect(block).height())
            blockNumber += 1

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            block = self._editor.firstVisibleBlock()
            current_y = int(
                self._editor.blockBoundingGeometry(block)
                .translated(self._editor.contentOffset())
                .top()
            )

            line_number = -1
            while block.isValid() and current_y <= event.pos().y():
                if block.isVisible():
                    if (
                        event.pos().y()
                        < current_y + self._editor.blockBoundingRect(block).height()
                    ):
                        line_number = block.blockNumber()
                        break
                block = block.next()
                current_y += self._editor.blockBoundingRect(block).height()

            if line_number == -1:
                return

            if line_number in self.breakpoints:
                self.try_remove_breakpoint.emit(line_number + 1)
            else:
                self.try_add_breakpoint.emit(line_number + 1)


class CodeEditor(QPlainTextEdit):
    try_add_breakpoint = Signal(int)
    try_remove_breakpoint = Signal(int)

    _HIGHLIGHT_COLOR = QColor(230, 240, 255)
    _TAB_SPACES = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lineNumberArea = LineNumberArea(self)
        self._highlighter = PythonHighlighter(self.document())
        self._highlighted_line_block = None

        self.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.setTabStopDistance(
            QFontMetrics(self.font()).horizontalAdvance(" ") * self._TAB_SPACES
        )

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)

        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self._executed_line_highlight_format = QTextCharFormat()
        self._executed_line_highlight_format.setBackground(self._HIGHLIGHT_COLOR)

        self._lineNumberArea.try_add_breakpoint.connect(self.try_add_breakpoint)
        self._lineNumberArea.try_remove_breakpoint.connect(self.try_remove_breakpoint)

    def line_number_area_width(self):
        digits = 1
        max_value = max(1, self.blockCount())
        while max_value >= 10:
            max_value /= 10
            digits += 1

        number_width = self.fontMetrics().horizontalAdvance("9") * digits
        icon_diameter = self._lineNumberArea.icon_radius * 2
        total_width = (
            self._lineNumberArea.icon_margin
            + icon_diameter
            + self._lineNumberArea._ICON_NUMBER_SPACING
            + number_width
            + self._lineNumberArea.number_right_margin
        )
        return total_width

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self._lineNumberArea.scroll(0, dy)
        else:
            self._lineNumberArea.update(
                0, rect.y(), self._lineNumberArea.width(), rect.height()
            )

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def highlight_current_line(self):
        extraSelections = []
        if self._highlighted_line_block:
            selection = QTextEdit.ExtraSelection()
            selection.format = self._executed_line_highlight_format
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            cursor = self.textCursor()
            cursor.setPosition(self._highlighted_line_block.position())
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            selection.cursor = cursor
            extraSelections.append(selection)

        self.setExtraSelections(extraSelections)

    def clear_highlighting(self):
        self._highlighted_line_block = None
        self.setExtraSelections([])
        self.highlight_current_line()

    def highlight_executed_line(self, line_number):
        self.clear_highlighting()

        block = self.document().findBlockByNumber(line_number - 1)
        if block.isValid():
            self._highlighted_line_block = block
            self.highlight_current_line()
            cursor = QTextCursor(block)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()

    def add_breakpoint(self, breakpoint):
        self._lineNumberArea.breakpoints.add(breakpoint - 1)
        self._lineNumberArea.update()

    def remove_breakpoint(self, breakpoint):
        self._lineNumberArea.breakpoints.remove(breakpoint - 1)
        self._lineNumberArea.update()

    def get_breakpoints(self):
        return {bp + 1 for bp in self._lineNumberArea.breakpoints}

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._lineNumberArea.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def keyPressEvent(self, event):
        if (
            event.key() in (Qt.Key_Enter, Qt.Key_Return)
            and event.modifiers() == Qt.ShiftModifier
        ):
            event = QKeyEvent(event.type(), event.key(), Qt.NoModifier, event.text())
        super().keyPressEvent(event)


SOURCE_CODE_FILE_NAME = "<string>"


def returns_bool_on_exception(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
            return True
        except Exception as e:
            print(f"func = {func} | e = {e}")
            return False

    return wrapper


class SpecterDebugger(QObject):
    code_started = Signal()
    code_paused = Signal()
    code_finished = Signal(str)
    current_line_changed = Signal(int)
    output_received = Signal(str)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self._client = None
        self._server_proc = subprocess.Popen(
            [
                SPECTER_VIEVER_DEBUGGER_PATH,
                "server",
                "--host",
                SPECTER_VIEVER_DEBUGGER_HOST,
                "--port",
                str(SPECTER_VIEVER_DEBUGGER_PORT),
                "--autostart",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    @property
    def client(self):
        if not self._client:
            self._client = DebuggerClient(
                f"{SPECTER_VIEVER_DEBUGGER_HOST}:{SPECTER_VIEVER_DEBUGGER_PORT}"
            )

            session = self._client.create_session()
            self._session_id = session.id
            self._client.listen_events(self._session_id, self._on_event)
            self._client.set_source(
                self._session_id, SOURCE_CODE_FILE_NAME, "".encode("utf-8")
            )

        return self._client

    def _on_event(self, event):
        event_type = event.WhichOneof("event")

        if event_type == "line_changed_event":
            line_event = event.line_changed_event
            lineno = line_event.lineno
            self.current_line_changed.emit(lineno)

        elif event_type == "finished_event":
            finished_event = event.finished_event
            status = finished_event.status
            self.code_finished.emit(status)

        elif event_type == "started_event":
            self.code_started.emit()

        elif event_type == "paused_event":
            self.code_paused.emit()

        elif event_type == "stdout_event":
            stdout_event = event.stdout_event
            message = stdout_event.message
            self.output_received.emit(message)

        elif event_type == "stderr_event":
            stderr_event = event.stderr_event
            message = stderr_event.message
            self.error_occurred.emit(message)

    @returns_bool_on_exception
    def start(self):
        self.client.start(self._session_id)

    @returns_bool_on_exception
    def stop(self):
        self.client.stop(self._session_id)

    @returns_bool_on_exception
    def resume(self):
        self.client.resume(self._session_id)

    @returns_bool_on_exception
    def set_source(self, source: str):
        self.client.set_source(
            self._session_id, SOURCE_CODE_FILE_NAME, source.encode("utf-8")
        )

    @returns_bool_on_exception
    def add_breakpoint(self, breakpoint: int):
        self.client.add_breakpoint(self._session_id, SOURCE_CODE_FILE_NAME, breakpoint)

    @returns_bool_on_exception
    def remove_breakpoint(self, breakpoint: int):
        self.client.remove_breakpoint(
            self._session_id, SOURCE_CODE_FILE_NAME, breakpoint
        )


class EditorDock(QDockWidget):
    CONSOLE_BG_COLOR = QColor("#282c34")
    CONSOLE_TEXT_COLOR = QColor("#abb2bf")
    ERROR_TEXT_COLOR = QColor("#e06c75")

    def __init__(self, client: Client = None):
        super().__init__("Editor")
        self._client = client
        self._debugger = SpecterDebugger()

        self._init_ui()
        self._init_connections()

    def _init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)

        top_layout = QHBoxLayout()

        self._start_button = self._make_tool_button("New/Run", ":/icons/start.png")
        self._stop_button = self._make_tool_button("Stop", ":/icons/stop.png")
        self._resume_button = self._make_tool_button("Continue", ":/icons/resume.png")

        top_layout.addWidget(self._start_button)
        top_layout.addWidget(self._stop_button)
        top_layout.addWidget(self._resume_button)
        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        self._code_editor = CodeEditor(self)
        self._code_editor.setPlaceholderText("Enter code here...")

        main_layout.addWidget(self._code_editor)

        self._output_console = QTextEdit(self)
        self._output_console.setReadOnly(True)
        self._output_console.setPlaceholderText("Program output will appear here...")
        self._output_console.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        self._output_console.setFixedHeight(150)

        palette = self._output_console.palette()
        palette.setColor(QPalette.ColorRole.Base, EditorDock.CONSOLE_BG_COLOR)
        palette.setColor(QPalette.ColorRole.Text, EditorDock.CONSOLE_TEXT_COLOR)
        palette.setColor(
            QPalette.ColorRole.PlaceholderText, EditorDock.CONSOLE_TEXT_COLOR
        )

        self._output_console.setPalette(palette)

        font = QFont("Consolas")
        self._output_console.setFont(font)

        main_layout.addWidget(self._output_console)

        self.setWidget(main_widget)
        self._update_states(running=False, paused=False)

    def _init_connections(self):
        self._start_button.clicked.connect(self._on_start_clicked)
        self._stop_button.clicked.connect(self._on_stop_clicked)
        self._resume_button.clicked.connect(self._on_resume_clicked)

        self._code_editor.textChanged.connect(self._on_code_changed)
        self._code_editor.try_add_breakpoint.connect(self._on_try_add_breakpoint)
        self._code_editor.try_remove_breakpoint.connect(self._on_try_remove_breakpoint)

        self._debugger.code_started.connect(self._on_code_started)
        self._debugger.code_finished.connect(self._on_code_finished)
        self._debugger.code_paused.connect(self.on_code_paused)
        self._debugger.current_line_changed.connect(self._on_current_line_changed)
        self._debugger.output_received.connect(self._on_output_received)
        self._debugger.error_occurred.connect(self._on_error_occurred)

    def _make_tool_button(self, tooltip: str, icon_path: str) -> QToolButton:
        btn = QToolButton()
        try:
            btn.setIcon(QIcon(QPixmap(icon_path)))
        except Exception:
            print(f"Warning: Icon not found at {icon_path}. Using default.")
            btn.setText(tooltip)

        btn.setToolTip(tooltip)
        btn.setAutoRaise(True)
        btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        return btn

    def _update_states(self, running: bool, paused: bool):
        self._start_button.setEnabled(not running)
        self._stop_button.setEnabled(running)
        self._resume_button.setEnabled(running and paused)
        self._code_editor.setReadOnly(running)

    def _on_start_clicked(self):
        self._output_console.clear()
        self._code_editor.clear_highlighting()
        self._debugger.start()
        self._update_states(running=True, paused=False)

    def _on_stop_clicked(self):
        self._debugger.stop()
        self._code_editor.clear_highlighting()

    def _on_resume_clicked(self):
        self._debugger.resume()
        self._update_states(running=True, paused=False)

    def _on_code_started(self):
        self._output_console.append("--- Code Execution Started ---\n")

    def _on_code_finished(self, status: str):
        self._output_console.append(f"--- Code Execution Finished ({status}) ---\n")
        self._update_states(running=False, paused=False)
        self._code_editor.clear_highlighting()

    def on_code_paused(self):
        self._update_states(running=True, paused=True)

    def _on_current_line_changed(self, line_number: int):
        self._code_editor.highlight_executed_line(line_number)

    def _on_output_received(self, text: str):
        self._output_console.insertPlainText(text)
        self._output_console.verticalScrollBar().setValue(
            self._output_console.verticalScrollBar().maximum()
        )

    def _on_error_occurred(self, error_msg: str):
        cursor = self._output_console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        error_format = QTextCharFormat()
        error_format.setForeground(EditorDock.ERROR_TEXT_COLOR)
        error_format.setFontWeight(QFont.Bold)

        cursor.insertBlock()
        cursor.setCharFormat(error_format)
        cursor.insertText("--- ERROR ---")

        cursor.insertBlock()
        cursor.insertText(f"{error_msg}\n")

        cursor.movePosition(QTextCursor.MoveOperation.End)
        default_format = QTextCharFormat()
        cursor.setCharFormat(default_format)

        self._output_console.setTextCursor(cursor)

        self._output_console.verticalScrollBar().setValue(
            self._output_console.verticalScrollBar().maximum()
        )
        self._update_states(running=False, paused=False)
        self._code_editor.clear_highlighting()

    def _on_code_changed(self):
        self._code_editor.clear_highlighting()
        code = self._code_editor.toPlainText()
        self._debugger.set_source(code)

    def _on_try_add_breakpoint(self, breakpoint_lineno: int):
        if self._debugger.add_breakpoint(breakpoint_lineno):
            self._code_editor.add_breakpoint(breakpoint_lineno)

    def _on_try_remove_breakpoint(self, breakpoint_lineno: int):
        if self._debugger.remove_breakpoint(breakpoint_lineno):
            self._code_editor.remove_breakpoint(breakpoint_lineno)
