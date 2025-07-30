import linecache
import builtins
import traceback
import bdb
import sys
import io

from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QTextEdit,
    QPlainTextEdit,
    QHBoxLayout,
    QVBoxLayout,
    QSizePolicy,
    QToolButton,
)
from PySide6.QtCore import (
    Qt,
    QObject,
    QMetaObject,
    QRegularExpression,
    QSize,
    Slot,
    Signal,
    QRect,
    QThread,
    QMutex,
    QWaitCondition,
    Q_ARG,
)
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
)

from specterui.client import Client


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(Qt.darkBlue))
        keyword_format.setFontWeight(QFont.Bold)

        keywords = [
            "False",
            "None",
            "True",
            "and",
            "as",
            "assert",
            "async",
            "await",
            "break",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "nonlocal",
            "not",
            "or",
            "pass",
            "raise",
            "return",
            "try",
            "while",
            "with",
            "yield",
        ]
        self._rules = []
        for word in keywords:
            self._rules.append((r"\b" + word + r"\b", keyword_format))

        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor(Qt.darkMagenta))
        builtin_format.setFontWeight(QFont.Bold)
        builtins = [
            "abs",
            "all",
            "any",
            "ascii",
            "bin",
            "bool",
            "bytearray",
            "bytes",
            "callable",
            "chr",
            "classmethod",
            "compile",
            "complex",
            "delattr",
            "dict",
            "dir",
            "divmod",
            "enumerate",
            "eval",
            "exec",
            "filter",
            "float",
            "format",
            "frozenset",
            "getattr",
            "globals",
            "hasattr",
            "hash",
            "help",
            "hex",
            "id",
            "input",
            "int",
            "isinstance",
            "issubclass",
            "iter",
            "len",
            "list",
            "locals",
            "map",
            "max",
            "memoryview",
            "min",
            "next",
            "object",
            "oct",
            "open",
            "ord",
            "pow",
            "print",
            "property",
            "range",
            "repr",
            "reversed",
            "round",
            "set",
            "setattr",
            "slice",
            "sorted",
            "staticmethod",
            "str",
            "sum",
            "super",
            "tuple",
            "type",
            "vars",
            "zip",
        ]
        for word in builtins:
            self._rules.append((r"\b" + word + r"\b", builtin_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor(Qt.darkGreen))
        self._rules.append((r'".*?"', string_format))
        self._rules.append((r"'.*?'", string_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor(Qt.darkCyan))
        self._rules.append((r"\b[0-9]+\b", number_format))
        self._rules.append((r"\b[0-9]*\.[0-9]+\b", number_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(Qt.gray))
        comment_format.setFontItalic(True)
        self._rules.append((r"#.*", comment_format))

        class_function_format = QTextCharFormat()
        class_function_format.setForeground(QColor(Qt.darkRed))
        class_function_format.setFontWeight(QFont.Bold)
        self._rules.append((r"\bclass\s+[A-Za-z_][A-Za-z0-9_]*", class_function_format))
        self._rules.append((r"\bdef\s+[A-Za-z_][A-Za-z0-9_]*", class_function_format))

        self._multi_line_comment_format = QTextCharFormat()
        self._multi_line_comment_format.setForeground(QColor(Qt.gray))
        self._multi_line_comment_format.setFontItalic(True)

        self._triple_quotes_regex_pattern = r'"""|\'\'\''

    def highlightBlock(self, text):
        for pattern_string, format in self._rules:
            expression = QRegularExpression(pattern_string)
            it = expression.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

        self.setCurrentBlockState(0)

        startIndex = 0
        if self.previousBlockState() != 1:
            triple_quotes_re = QRegularExpression(self._triple_quotes_regex_pattern)
            match = triple_quotes_re.match(text)
            if match.hasMatch():
                startIndex = match.capturedStart()
            else:
                startIndex = -1
        else:
            startIndex = 0

        while startIndex >= 0:
            triple_quotes_re = QRegularExpression(self._triple_quotes_regex_pattern)
            end_match = triple_quotes_re.match(text, startIndex + 3)

            if not end_match.hasMatch():
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex
            else:
                endIndex = end_match.capturedStart()
                commentLength = endIndex - startIndex + end_match.capturedLength()
                self.setCurrentBlockState(0)

            self.setFormat(startIndex, commentLength, self._multi_line_comment_format)

            next_start_match = triple_quotes_re.match(text, startIndex + commentLength)
            if next_start_match.hasMatch():
                startIndex = next_start_match.capturedStart()
            else:
                startIndex = -1


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


class CustomStream(QObject):
    text_written = Signal(str)

    def write(self, text):
        if text:
            self.text_written.emit(text)

    def flush(self):
        pass


class DebuggerThread(QThread, bdb.Bdb):
    code_started = Signal()
    code_finished = Signal(str)
    current_line_changed = Signal(int)
    output_received = Signal(str)
    error_occurred = Signal(str)
    breakpoint_toggled = Signal(int, bool)

    def __init__(self, parent=None):
        QThread.__init__(self, parent)
        bdb.Bdb.__init__(self)

        self._filename = "<string>"
        self._source_string = ""
        self._source_lines = []
        self._enter_frame = None

        self._globals_dict = {}
        self._locals_dict = {}

        self._stop_requested = False
        self._current_frame = None

        self._pause_mutex = QMutex()
        self._pause_condition = QWaitCondition()
        self._is_paused = False

        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

        self._custom_stdout = CustomStream()
        self._custom_stderr = CustomStream()

        self._custom_stdout.text_written.connect(self.output_received.emit)
        self._custom_stderr.text_written.connect(self.output_received.emit)

    def _populate_linecache(self):
        if self._source_string and self._source_lines:
            linecache.cache[self._filename] = (
                len(self._source_string),
                0,
                self._source_lines,
                self._filename,
            )

    @Slot(str)
    def set_source(self, source_string: str):
        self.clear_all_breakpoints()
        self._source_string = source_string
        self._source_lines = self._source_string.splitlines(keepends=True)
        self._populate_linecache()

    @Slot(dict, dict)
    def set_context(self, globals_dict: dict, locals_dict: dict):
        self._globals_dict = globals_dict
        self._locals_dict = locals_dict

    def run(self):
        self._stop_requested = False
        self._is_paused = False
        self._error_already_reported = False

        self._captured_output = io.StringIO()
        sys.stdout = self._custom_stdout
        sys.stderr = self._custom_stderr

        self.code_started.emit()
        result_status = "error"

        try:
            self.set_trace()
            exec(self._source_string, self._globals_dict, self._locals_dict)
            result_status = "success"
        except bdb.BdbQuit:
            result_status = "stopped"
        except Exception:
            if not self._error_already_reported:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                formatted_traceback = self._format_user_traceback(
                    exc_type, exc_value, exc_traceback
                )
                self.error_occurred.emit(f"Runtime Error:\n{formatted_traceback}")
            result_status = "error"
        finally:
            sys.stdout = self._original_stdout
            sys.stderr = self._original_stderr

            self.code_finished.emit(result_status)

            self._pause_mutex.lock()
            self._is_paused = False
            self._pause_condition.wakeAll()
            self._pause_mutex.unlock()

    @Slot()
    def stop_execution(self):
        self._stop_requested = True
        self._pause_mutex.lock()

        if self._is_paused:
            self._is_paused = False
            self._pause_condition.wakeAll()
        self._pause_mutex.unlock()

    @Slot()
    def continue_execution(self):
        self.set_continue()
        self._pause_mutex.lock()
        if self._is_paused:
            self._is_paused = False
            self._pause_condition.wakeAll()
        self._pause_mutex.unlock()

    @Slot(int)
    def set_breakpoint(self, lineno: int):
        self._populate_linecache()
        result = self.set_break(self._filename, lineno)
        if result is None:
            self.breakpoint_toggled.emit(lineno, True)

    @Slot(int)
    def clear_breakpoint(self, lineno: int):
        result = self.clear_break(self._filename, lineno)
        if result is None:
            self.breakpoint_toggled.emit(lineno, False)

    @Slot()
    def clear_all_breakpoints(self):
        self.clear_all_breaks()

    def user_line(self, frame):
        if self._stop_requested:
            raise bdb.BdbQuit

        filename = self.canonic(frame.f_code.co_filename)
        lineno = frame.f_lineno

        if self._filename == filename:
            self._current_frame = frame
            self.current_line_changed.emit(lineno)

            if self._is_break(filename, lineno):
                self._pause_mutex.lock()
                self._is_paused = True
                while self._is_paused and not self._stop_requested:
                    self._pause_condition.wait(self._pause_mutex)
                self._pause_mutex.unlock()

                if self._stop_requested:
                    raise bdb.BdbQuit

    def user_exception(self, frame, exc_info):
        if not self._error_already_reported:
            formatted_traceback = self._format_user_traceback(
                exc_info[0], exc_info[1], exc_info[2]
            )
            self.error_occurred.emit(f"Exception in user code:\n{formatted_traceback}")
            self._error_already_reported = True

    def _is_break(self, filename, lineno):
        breaks_for_file = self.get_all_breaks().get(filename)
        return breaks_for_file is not None and lineno in breaks_for_file

    def _format_user_traceback(self, exc_type, exc_value, exc_traceback):
        formatted_lines = ["Traceback (most recent call last):"]
        extracted_tb = traceback.extract_tb(exc_traceback)

        user_code_frames = []
        for frame_summary in extracted_tb:
            if self.canonic(frame_summary.filename) == self._filename:
                user_code_frames.append(frame_summary)

        if not user_code_frames:
            user_code_frames = extracted_tb

        for frame_summary in user_code_frames:
            formatted_lines.append(
                f'  File "{frame_summary.filename}", line {frame_summary.lineno}, in {frame_summary.name}'
            )
            if frame_summary.line:
                formatted_lines.append(f"    {frame_summary.line.strip()}")

        formatted_lines.append(f"{exc_type.__name__}: {exc_value}")

        return "\n".join(formatted_lines)


class EditorDock(QDockWidget):
    CONSOLE_BG_COLOR = QColor("#282c34")
    CONSOLE_TEXT_COLOR = QColor("#abb2bf")
    ERROR_TEXT_COLOR = QColor("#e06c75")

    def __init__(self, client=None):
        super().__init__("Editor")
        self._client = client

        self._init_ui()
        self._init_connections()
        self._create_debugger()

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

    def _create_debugger(self):
        if getattr(self, "_debugger", None) and self._debugger.isRunning():
            self._debugger.stop_execution()
            self._debugger.wait()
            self._debugger.code_started.disconnect(self._on_code_started)
            self._debugger.code_finished.disconnect(self._on_code_finished)
            self._debugger.current_line_changed.disconnect(
                self._on_current_line_changed
            )
            self._debugger.output_received.disconnect(self._on_output_received)
            self._debugger.error_occurred.disconnect(self._on_error_occurred)
            self._debugger.breakpoint_toggled.disconnect(self._on_breakpoint_toggled)
            self._debugger = None

        self._debugger = DebuggerThread(self)

        self._debugger.code_started.connect(self._on_code_started)
        self._debugger.code_finished.connect(self._on_code_finished)
        self._debugger.current_line_changed.connect(self._on_current_line_changed)
        self._debugger.output_received.connect(self._on_output_received)
        self._debugger.error_occurred.connect(self._on_error_occurred)
        self._debugger.breakpoint_toggled.connect(self._on_breakpoint_toggled)

        self._debugger.finished.connect(self._create_debugger)

        self._code_editor.clear_highlighting()
        code = self._code_editor.toPlainText()
        self._debugger.set_source(code)

        for bp_line in list(self._code_editor.get_breakpoints()):
            self._debugger.set_breakpoint(bp_line)

        self._debugger.set_context(
            globals_dict=self._get_globals_context(),
            locals_dict=self._get_locals_context(),
        )

    def _on_start_clicked(self):
        self._output_console.clear()
        self._code_editor.clear_highlighting()
        self._update_states(running=True, paused=False)

        self._debugger.start()

    def _get_globals_context(self):
        globals_context = {
            "__builtins__": builtins,
        }
        return globals_context

    def _get_locals_context(self):
        return {}

    def _on_stop_clicked(self):
        self._debugger.stop_execution()
        self._code_editor.clear_highlighting()

    def _on_resume_clicked(self):
        self._update_states(running=True, paused=False)
        self._debugger.continue_execution()

    def _on_code_started(self):
        self._output_console.append("--- Code Execution Started ---\n")

    def _on_code_finished(self, status: str):
        self._output_console.append(f"--- Code Execution Finished ({status}) ---\n")
        self._update_states(running=False, paused=False)
        self._code_editor.clear_highlighting()

    def _on_current_line_changed(self, line_number: int):
        self._update_states(running=True, paused=self._debugger._is_paused)
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

        for bp_line in list(self._code_editor.get_breakpoints()):
            self._debugger.set_breakpoint(bp_line)

    def _on_try_add_breakpoint(self, breakpoint_lineno: int):
        QMetaObject.invokeMethod(
            self._debugger,
            "set_breakpoint",
            Qt.QueuedConnection,
            Q_ARG(int, breakpoint_lineno),
        )

    def _on_try_remove_breakpoint(self, breakpoint_lineno: int):
        QMetaObject.invokeMethod(
            self._debugger,
            "clear_breakpoint",
            Qt.QueuedConnection,
            Q_ARG(int, breakpoint_lineno),
        )

    @Slot(int, str)
    def _on_breakpoint_toggled(self, breakpoint_lineno: int, toggled: True):
        if toggled:
            self._code_editor.add_breakpoint(breakpoint_lineno)
        else:
            self._code_editor.remove_breakpoint(breakpoint_lineno)
