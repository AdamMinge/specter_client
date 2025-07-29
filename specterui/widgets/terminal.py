import sys
import io
import re
import traceback

from PySide6.QtWidgets import (
    QDockWidget,
    QTextEdit,
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QTextCursor,
    QSyntaxHighlighter,
    QTextCharFormat,
    QColor,
    QFont,
)

from specterui.client import Client


class QTextEditStream(io.StringIO):
    def __init__(self, text_edit: QTextEdit):
        super().__init__()
        self.text_edit = text_edit

    def write(self, s: str):
        super().write(s)

        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
        self.text_edit.insertPlainText(s)
        QApplication.processEvents()


class PythonHighlighter(QSyntaxHighlighter):
    NO_STATE = 0
    IN_SINGLE_QUOTE_TRIPLE = 1
    IN_DOUBLE_QUOTE_TRIPLE = 2

    def __init__(self, document, text_edit_widget: QTextEdit):
        super().__init__(document)
        self._text_edit_widget = text_edit_widget
        self.highlighting_rules = []

        self.formats = {}
        self.formats["keyword"] = self._create_format("#c678dd", QFont.Weight.Bold)
        self.formats["string"] = self._create_format("#98c379")
        self.formats["number"] = self._create_format("#d19a66")
        self.formats["comment"] = self._create_format("#5c6370", font_italic=True)
        self.formats["class_function"] = self._create_format("#61afef")
        self.formats["operator"] = self._create_format("#e06c75")
        self.formats["builtin"] = self._create_format("#e5c07b")
        self.formats["self"] = self._create_format("#e06c75", font_italic=True)

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
        self.highlighting_rules.append(
            (re.compile(r"\b(" + "|".join(keywords) + r")\b"), self.formats["keyword"])
        )

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
            "__import__",
        ]
        self.highlighting_rules.append(
            (re.compile(r"\b(" + "|".join(builtins) + r")\b"), self.formats["builtin"])
        )

        operators = [
            "=",
            "==",
            "!=",
            "<",
            "<=",
            ">",
            ">=",
            r"\+",
            "-",
            r"\*",
            "/",
            "//",
            r"\%",
            r"\*\*",
            r"\+=",
            r"-=",
            r"\*=",
            r"/=",
            r"\%=",
            r"\*\*=",
            r"//=",
            r"&=",
            r"\|=",
            r"\^=",
            r">>=",
            r"<<=",
            "&",
            r"\|",
            r"\^",
            "~",
            ">>",
            "<<",
            r"\.",
            r",",
            r":",
            r";",
            r"@",
            r"->",
        ]
        self.highlighting_rules.append(
            (
                re.compile(r"(" + "|".join(re.escape(op) for op in operators) + r")"),
                self.formats["operator"],
            )
        )

        self.highlighting_rules.append(
            (
                re.compile(
                    r"\b(0x[0-9a-fA-F]+|0o[0-7]+|0b[01]+|[0-9]*\.[0-9]+([eE][+-]?[0-9]+)?|[0-9]+)\b"
                ),
                self.formats["number"],
            )
        )

        self.highlighting_rules.append(
            (re.compile(r"#[^\n]*"), self.formats["comment"])
        )

        self.highlighting_rules.append(
            (
                re.compile(r"\b(class|def)\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
                self.formats["class_function"],
            )
        )

        self.highlighting_rules.append((re.compile(r"\bself\b"), self.formats["self"]))

        self.tri_single = (re.compile(r"'''"), self.formats["string"])
        self.tri_double = (re.compile(r'"""'), self.formats["string"])

        self.string_regex = re.compile(
            r"(?:[rR]|[fF]|[bB])?\"[^\"\\\n]*(?:\\.[^\"\\\n]*)*\"|'(?:[rR]|[fF]|[bB])?'[^'\\\n]*(?:\\.[^'\\\n]*)*'"
        )
        self.highlighting_rules.append((self.string_regex, self.formats["string"]))

    def _create_format(
        self,
        color_hex: str,
        font_weight: QFont.Weight = QFont.Weight.Normal,
        font_italic: bool = False,
    ):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color_hex))
        fmt.setFontWeight(font_weight)
        fmt.setFontItalic(font_italic)
        return fmt

    def highlightBlock(self, text: str):
        default_text_color = self._text_edit_widget.palette().text().color()
        self.setFormat(0, len(text), default_text_color)

        current_state = self.previousBlockState()

        start_index = 0
        if current_state == self.IN_SINGLE_QUOTE_TRIPLE:
            start_index = self.highlightMultiLine(text, self.tri_single, start_index)
        elif current_state == self.IN_DOUBLE_QUOTE_TRIPLE:
            start_index = self.highlightMultiLine(text, self.tri_double, start_index)

        for pattern, format in self.highlighting_rules:
            if pattern == self.string_regex:
                for match in pattern.finditer(text, start_index):
                    self.setFormat(match.start(), match.end() - match.start(), format)
                continue

            for match in pattern.finditer(text, start_index):
                if pattern.pattern.startswith(r"\b(class|def)"):
                    start = match.start(2)
                    length = match.end(2) - start
                else:
                    start = match.start()
                    length = match.end()
                self.setFormat(start, length, format)

        self.setCurrentBlockState(self.NO_STATE)
        start_index = self.highlightMultiLine(text, self.tri_single, 0)
        if start_index == 0:
            start_index = self.highlightMultiLine(text, self.tri_double, 0)

    def highlightMultiLine(self, text: str, delimiter: tuple, start_index: int) -> int:
        pattern, format = delimiter
        match = pattern.search(text, start_index)
        while match:
            if self.previousBlockState() == self.NO_STATE:
                self.setCurrentBlockState(
                    self.IN_SINGLE_QUOTE_TRIPLE
                    if delimiter == self.tri_single
                    else self.IN_DOUBLE_QUOTE_TRIPLE
                )
                self.setFormat(match.start(), len(text) - match.start(), format)
            else:
                self.setCurrentBlockState(self.NO_STATE)
                self.setFormat(0, match.end(), format)

            start_index = match.end()
            match = pattern.search(text, start_index)

        if self.currentBlockState() != self.NO_STATE:
            self.setFormat(start_index, len(text) - start_index, format)

        return start_index


class TerminalDock(QDockWidget):
    def __init__(self, client: Client):
        super().__init__("Terminal")
        self._client = client
        self._init_ui()
        self._setup_execution_environment()
        self._history = []
        self._history_index = -1
        self._highlighter = PythonHighlighter(
            self._output_area.document(), self._output_area
        )

    def _init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        self._output_area = QTextEdit()
        self._output_area.setReadOnly(True)
        self._output_area.setStyleSheet(
            "background-color: #282c34; color: #abb2bf; font-family: monospace;"
        )
        main_layout.addWidget(self._output_area)

        input_layout = QHBoxLayout()
        self._input_line = QLineEdit()
        self._input_line.setStyleSheet(
            "background-color: #3b4048; color: #e06c75; font-family: monospace;"
        )
        self._input_line.returnPressed.connect(self._execute_command)
        self._input_line.installEventFilter(self)

        self._clear_button = QPushButton("Clear")
        self._clear_button.clicked.connect(self._output_area.clear)

        input_layout.addWidget(self._input_line)
        input_layout.addWidget(self._clear_button)
        main_layout.addLayout(input_layout)

        self.setWidget(central_widget)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        self._output_area.append("# Welcome to the SpecterUI Terminal!")
        self._output_area.append("# Available objects: 'client'")
        self._output_area.append("# Use Up/Down arrows for history.")

    def _setup_execution_environment(self):
        self._execution_globals = {
            "__builtins__": __builtins__,
            "client": self._client,
        }
        self._execution_locals = self._execution_globals.copy()

    def _execute_command(self):
        command = self._input_line.text().strip()
        self._input_line.clear()

        if not command:
            return

        self._history.append(command)
        self._history_index = len(self._history)

        self._output_area.append(f">>> {command}\n")

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = QTextEditStream(self._output_area)
        sys.stderr = QTextEditStream(self._output_area)

        try:
            result = eval(command, self._execution_globals, self._execution_locals)
            if result is not None:
                self._output_area.append(repr(result))
        except SyntaxError:
            try:
                exec(command, self._execution_globals, self._execution_locals)
            except Exception:
                self._output_area.append(
                    f"<span style='color: #e06c75;'>{traceback.format_exc()}</span>"
                )
        except Exception:
            self._output_area.append(
                f"<span style='color: #e06c75;'>{traceback.format_exc()}</span>"
            )
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self._output_area.ensureCursorVisible()

    def eventFilter(self, obj, event):
        if obj == self._input_line and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Up:
                self._history_index = max(0, self._history_index - 1)
                if self._history:
                    self._input_line.setText(self._history[self._history_index])
                return True
            elif event.key() == Qt.Key.Key_Down:
                self._history_index = min(len(self._history), self._history_index + 1)
                if self._history_index < len(self._history):
                    self._input_line.setText(self._history[self._history_index])
                else:
                    self._input_line.clear()
                return True
        return super().eventFilter(obj, event)
