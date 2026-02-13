#!/usr/bin/env python3
"""
PIC Readable Assembly IDE
=========================
A PyQt5 IDE inspired by MPLAB IDE v8.92.

Features:
  - Project tree (left panel)
  - Tabbed code editor with syntax highlighting for .rasm / .asm files
  - Output / Build window (bottom panel)
  - Integrated forward translator (.rasm → .asm)
  - Integrated reverse translator (.asm → .rasm)
  - File management (New, Open, Save, Save As, Close)
  - Find / Replace
  - MPLAB v8.92 visual style (classic grey/blue theme)
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import shutil

from PyQt5.QtCore import (
    QDir,
    QFileInfo,
    QModelIndex,
    QProcess,
    QRegExp,
    QSettings,
    QSize,
    QStringListModel,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPalette,
    QPixmap,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFileSystemModel,
    QFontDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
    qApp,
)

# ---------------------------------------------------------------------------
# Paths — handle both normal run and PyInstaller frozen exe
# ---------------------------------------------------------------------------
_IDE_DIR = Path(__file__).resolve().parent

if getattr(sys, "frozen", False):
    # Running as PyInstaller exe — bundled data is in sys._MEIPASS
    _BUNDLE_DIR = Path(sys._MEIPASS)
    _PROJECT_ROOT = Path(sys.executable).resolve().parent
    _INSTRUCTIONS_DIR = _BUNDLE_DIR / "instructions"
    _TRANSLATOR = _BUNDLE_DIR / "pic18_translator.py"
    _REVERSE_TRANSLATOR = _BUNDLE_DIR / "pic18_reverse_translator.py"
else:
    _PROJECT_ROOT = _IDE_DIR.parent
    _INSTRUCTIONS_DIR = _PROJECT_ROOT / "instructions"
    _TRANSLATOR = _PROJECT_ROOT / "pic18_translator.py"
    _REVERSE_TRANSLATOR = _PROJECT_ROOT / "pic18_reverse_translator.py"

# ---------------------------------------------------------------------------
# Microchip Assembler auto-detection
# ---------------------------------------------------------------------------

def _find_mpasmx() -> str | None:
    """Search for mpasmx.exe (MPASM) in common Microchip install locations."""
    candidates = [
        # MPLAB X bundled MPASM
        Path(r"C:\Program Files\Microchip\MPLABX"),
        Path(r"C:\Program Files (x86)\Microchip\MPLABX"),
        # Legacy MPLAB IDE 8.x
        Path(r"C:\Program Files\Microchip\MPASM Suite"),
        Path(r"C:\Program Files (x86)\Microchip\MPASM Suite"),
    ]
    for base in candidates:
        if not base.exists():
            continue
        # Walk to find mpasmx.exe or mpasm.exe
        for name in ("mpasmx.exe", "mpasm.exe"):
            for hit in base.rglob(name):
                return str(hit)
    return None


def _find_pic_as() -> str | None:
    """Search for pic-as.exe (XC8 PIC Assembler) in common install locations."""
    candidates = [
        Path(r"C:\Program Files\Microchip\xc8"),
        Path(r"C:\Program Files (x86)\Microchip\xc8"),
    ]
    for base in candidates:
        if not base.exists():
            continue
        for hit in base.rglob("pic-as.exe"):
            return str(hit)
    return None


def _find_gpasm() -> str | None:
    """Search for gpasm.exe (open-source gputils assembler) on PATH."""
    path = shutil.which("gpasm")
    return path if path else None


def _auto_detect_assembler() -> tuple[str, str]:
    """Auto-detect a PIC assembler. Returns (type, path) or ('none', '').

    type is one of: 'mpasmx', 'pic-as', 'gpasm', 'none'.
    """
    p = _find_mpasmx()
    if p:
        return ("mpasmx", p)
    p = _find_pic_as()
    if p:
        return ("pic-as", p)
    p = _find_gpasm()
    if p:
        return ("gpasm", p)
    return ("none", "")


# ---------------------------------------------------------------------------
# PICkit / Programmer auto-detection
# ---------------------------------------------------------------------------

def _find_pk2cmd() -> str | None:
    """Search for pk2cmd.exe (PICkit 2 command-line tool)."""
    # Check PATH first
    p = shutil.which("pk2cmd")
    if p:
        return p
    candidates = [
        Path(r"C:\Program Files\Microchip\PICkit 2 v2"),
        Path(r"C:\Program Files (x86)\Microchip\PICkit 2 v2"),
        Path(r"C:\pk2cmd"),
        Path(r"C:\PICkit2"),
    ]
    for base in candidates:
        if not base.exists():
            continue
        for hit in base.rglob("pk2cmd.exe"):
            return str(hit)
    return None


def _find_ipecmd() -> str | None:
    """Search for ipecmd.exe (MPLAB IPE command-line — PICkit 3/4/SNAP)."""
    candidates = [
        Path(r"C:\Program Files\Microchip\MPLABX"),
        Path(r"C:\Program Files (x86)\Microchip\MPLABX"),
    ]
    for base in candidates:
        if not base.exists():
            continue
        for hit in base.rglob("ipecmd.exe"):
            return str(hit)
    return None


def _auto_detect_programmer() -> tuple[str, str]:
    """Auto-detect a PICkit programmer tool. Returns (type, path) or ('none', '').

    type is one of: 'pk2cmd', 'ipecmd', 'none'.
    """
    p = _find_ipecmd()
    if p:
        return ("ipecmd", p)
    p = _find_pk2cmd()
    if p:
        return ("pk2cmd", p)
    return ("none", "")


# Common PIC device names for the device selector combo box
_PIC_DEVICES = [
    "PIC16F84A", "PIC16F87", "PIC16F88",
    "PIC16F627A", "PIC16F628A", "PIC16F648A",
    "PIC16F873A", "PIC16F874A", "PIC16F876A", "PIC16F877A",
    "PIC16F882", "PIC16F883", "PIC16F884", "PIC16F886", "PIC16F887",
    "PIC16F1827", "PIC16F1847",
    "PIC16F1512", "PIC16F1513", "PIC16F1516", "PIC16F1517", "PIC16F1518", "PIC16F1519",
    "PIC16F15244", "PIC16F15245",
    "PIC16F18044", "PIC16F18045", "PIC16F18046",
    "PIC16F18144", "PIC16F18145", "PIC16F18146",
    "PIC16F18854", "PIC16F18855", "PIC16F18856", "PIC16F18857",
    "PIC16F18875", "PIC16F18876", "PIC16F18877",
    "PIC18F242", "PIC18F252", "PIC18F442", "PIC18F452",
    "PIC18F1220", "PIC18F1320", "PIC18F2220", "PIC18F2320",
    "PIC18F2420", "PIC18F2520", "PIC18F2550", "PIC18F2580",
    "PIC18F2620", "PIC18F2680",
    "PIC18F4420", "PIC18F4520", "PIC18F4550", "PIC18F4580",
    "PIC18F4620", "PIC18F4680",
    "PIC18F24K50", "PIC18F25K50", "PIC18F45K50",
    "PIC18F25K80", "PIC18F26K80", "PIC18F45K80", "PIC18F46K80",
    "PIC18F25Q10", "PIC18F45Q10", "PIC18F46Q10",
    "PIC18F26Q43", "PIC18F27Q43", "PIC18F46Q43", "PIC18F47Q43",
    "PIC18F26K42", "PIC18F27K42", "PIC18F46K42", "PIC18F47K42",
]

# ---------------------------------------------------------------------------
# Load readable instruction names from JSON for syntax highlighting
# ---------------------------------------------------------------------------

def _load_instruction_names() -> list[str]:
    """Return a flat list of all readable instruction names from JSON files."""
    names: list[str] = []
    for fname in ("pic18_instructions.json", "pic16_instructions.json"):
        path = _INSTRUCTIONS_DIR / fname
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for lang_map in data.values():
                names.extend(lang_map.keys())
    return names


_ALL_INSTRUCTION_NAMES = _load_instruction_names()


def _load_instruction_details() -> dict[str, str]:
    """Return a dict mapping readable name → PIC mnemonic for tooltip info."""
    details: dict[str, str] = {}
    for fname in ("pic18_instructions.json", "pic16_instructions.json"):
        path = _INSTRUCTIONS_DIR / fname
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for lang_map in data.values():
                for readable, mnemonic in lang_map.items():
                    details[readable] = mnemonic
    return details


_INSTRUCTION_DETAILS = _load_instruction_details()

# Directives recognized by the completer
_DIRECTIVES = [
    "ORG", "EQU", "SET", "LIST", "CONFIG", "__CONFIG", "END",
    "CBLOCK", "ENDC", "DB", "DW", "DT", "DE", "RES", "FILL",
    "PROCESSOR", "RADIX", "BANKSEL", "PAGESEL", "CONSTANT",
    "VARIABLE", "MACRO", "ENDM", "LOCAL", "EXITM", "INCLUDE",
    "#include", "#define", "#ifdef", "#ifndef", "#endif", "#else",
    "IF", "ELSE", "ENDIF", "WHILE", "ENDW",
    "MESSG", "ERROR", "ERRORLEVEL", "TITLE", "SUBTITLE",
    "PAGE", "SPACE", "NOLIST", "EXPAND", "NOEXPAND",
    "__IDLOCS", "__BADRAM", "__MAXRAM",
    "EXTERN", "GLOBAL", "CODE", "UDATA", "UDATA_SHR", "UDATA_ACS", "IDATA",
]

# Common PIC registers for the completer
_REGISTERS = [
    "WREG", "STATUS", "BSR", "PCL", "PCLATH", "PCLATU", "INTCON",
    "PRODL", "PRODH", "FSR0L", "FSR0H", "FSR1L", "FSR1H",
    "FSR2L", "FSR2H", "INDF0", "INDF1", "INDF2", "POSTINC0",
    "POSTINC1", "POSTINC2", "PREINC0", "PREINC1", "PREINC2",
    "POSTDEC0", "POSTDEC1", "POSTDEC2", "PLUSW0", "PLUSW1",
    "PLUSW2", "TBLPTRL", "TBLPTRH", "TBLPTRU", "TABLAT",
    "STKPTR", "TOSL", "TOSH", "TOSU",
    "PORTA", "PORTB", "PORTC", "PORTD", "PORTE",
    "LATA", "LATB", "LATC", "LATD", "LATE",
    "TRISA", "TRISB", "TRISC", "TRISD", "TRISE",
    "ACCESS", "BANKED",
]

# Full word list for the completer
_ALL_COMPLETIONS = sorted(
    set(_ALL_INSTRUCTION_NAMES + _DIRECTIVES + _REGISTERS),
    key=str.lower,
)

# ---------------------------------------------------------------------------
# MPLAB v8.92 colour palette
# ---------------------------------------------------------------------------
_BG_COLOR = "#F0F0F0"
_EDITOR_BG = "#FFFFFF"
_EDITOR_FG = "#000000"
_LINE_NUM_BG = "#E8E8E8"
_LINE_NUM_FG = "#808080"
_TOOLBAR_BG = "#D4D0C8"
_MENU_BG = "#D4D0C8"
_OUTPUT_BG = "#FFFFFF"
_OUTPUT_FG = "#000000"
_HIGHLIGHT_LINE = "#FFFFCC"
_STATUS_BG = "#D4D0C8"
_TREE_BG = "#FFFFFF"


# ═══════════════════════════════════════════════════════════════════════════
# Syntax Highlighter
# ═══════════════════════════════════════════════════════════════════════════

class RasmHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for .rasm and .asm files."""

    def __init__(self, parent: QTextDocument | None = None):
        super().__init__(parent)
        self._rules: list[tuple[QRegExp, QTextCharFormat]] = []
        self._build_rules()

    def _fmt(self, color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    def _build_rules(self) -> None:
        # Comments  (green, italic)
        comment_fmt = self._fmt("#008000", italic=True)
        self._rules.append((QRegExp(r";.*$"), comment_fmt))

        # Strings (brown)
        string_fmt = self._fmt("#A31515")
        self._rules.append((QRegExp(r'"[^"]*"'), string_fmt))

        # Numbers — hex
        num_fmt = self._fmt("#098658")
        self._rules.append((QRegExp(r"\b0[xX][0-9A-Fa-f]+\b"), num_fmt))
        # Numbers — binary
        self._rules.append((QRegExp(r"\b0[bB][01]+\b"), num_fmt))
        # Numbers — decimal
        self._rules.append((QRegExp(r"\b[0-9]+\b"), num_fmt))
        # Numbers — hex with h suffix
        self._rules.append((QRegExp(r"\b[0-9][0-9A-Fa-f]*[hH]\b"), num_fmt))

        # Directives (dark magenta, bold)
        dir_fmt = self._fmt("#8B008B", bold=True)
        directives = [
            "ORG", "EQU", "SET", "LIST", "CONFIG", "__CONFIG", "END",
            "CBLOCK", "ENDC", "DB", "DW", "DT", "DE", "RES", "FILL",
            "PROCESSOR", "RADIX", "BANKSEL", "PAGESEL", "CONSTANT",
            "VARIABLE", "MACRO", "ENDM", "LOCAL", "EXITM", "INCLUDE",
            "#include", "#INCLUDE", "#define", "#DEFINE", "#ifdef",
            "#IFDEF", "#ifndef", "#IFNDEF", "#endif", "#ENDIF",
            "#else", "#ELSE", "IF", "ELSE", "ENDIF", "WHILE", "ENDW",
            "MESSG", "ERROR", "ERRORLEVEL", "TITLE", "SUBTITLE",
            "PAGE", "SPACE", "NOLIST", "EXPAND", "NOEXPAND",
            "__IDLOCS", "__BADRAM", "__MAXRAM",
        ]
        for d in directives:
            self._rules.append((QRegExp(r"\b" + QRegExp.escape(d) + r"\b"), dir_fmt))

        # Readable instruction names (blue, bold)
        instr_fmt = self._fmt("#0000FF", bold=True)
        # Sort longest first to avoid partial matches in regex
        sorted_names = sorted(_ALL_INSTRUCTION_NAMES, key=len, reverse=True)
        # Build pattern in chunks to avoid regex overflow
        chunk_size = 50
        for i in range(0, len(sorted_names), chunk_size):
            chunk = sorted_names[i:i + chunk_size]
            pattern = r"\b(" + "|".join(QRegExp.escape(n) for n in chunk) + r")\b"
            self._rules.append((QRegExp(pattern), instr_fmt))

        # Standard PIC mnemonics (dark blue, bold)
        std_fmt = self._fmt("#00008B", bold=True)
        std_mnemonics = [
            "ADDWF", "ADDWFC", "ANDWF", "CLRF", "COMF", "CPFSEQ", "CPFSGT",
            "CPFSLT", "DECF", "DECFSZ", "DCFSNZ", "INCF", "INCFSZ", "INFSNZ",
            "IORWF", "MOVF", "MOVFF", "MOVWF", "MULWF", "NEGF", "RLCF",
            "RLNCF", "RRCF", "RRNCF", "SETF", "SUBFWB", "SUBWF", "SUBWFB",
            "SWAPF", "TSTFSZ", "XORWF", "BCF", "BSF", "BTFSC", "BTFSS",
            "BTG", "ADDLW", "ANDLW", "IORLW", "MOVLB", "MOVLW", "MULLW",
            "SUBLW", "XORLW", "BC", "BN", "BNC", "BNN", "BNOV", "BNZ",
            "BOV", "BRA", "BZ", "CALL", "CLRWDT", "DAW", "GOTO", "NOP",
            "POP", "PUSH", "RCALL", "RESET", "RETFIE", "RETLW", "RETURN",
            "SLEEP", "ADDFSR", "ADDULNK", "CALLW", "MOVSF", "MOVSS",
            "PUSHL", "SUBFSR", "SUBULNK", "CLRW", "RLF", "RRF", "OPTION",
            "TRIS", "LSLF", "LSRF", "ASRF", "BRW", "MOVIW", "MOVWI",
            "MOVLP",
        ]
        for m in std_mnemonics:
            self._rules.append((QRegExp(r"\b" + m + r"\b"), std_fmt))

        # Labels (dark red, bold)
        label_fmt = self._fmt("#800000", bold=True)
        self._rules.append((QRegExp(r"^\s*\w+:"), label_fmt))

        # Registers (teal)
        reg_fmt = self._fmt("#008080")
        regs = [
            "WREG", "STATUS", "BSR", "PCL", "PCLATH", "PCLATU", "INTCON",
            "PRODL", "PRODH", "FSR0L", "FSR0H", "FSR1L", "FSR1H",
            "FSR2L", "FSR2H", "INDF0", "INDF1", "INDF2", "POSTINC0",
            "POSTINC1", "POSTINC2", "PREINC0", "PREINC1", "PREINC2",
            "POSTDEC0", "POSTDEC1", "POSTDEC2", "PLUSW0", "PLUSW1",
            "PLUSW2", "TBLPTRL", "TBLPTRH", "TBLPTRU", "TABLAT",
            "STKPTR", "TOSL", "TOSH", "TOSU",
            "PORTA", "PORTB", "PORTC", "PORTD", "PORTE",
            "LATA", "LATB", "LATC", "LATD", "LATE",
            "TRISA", "TRISB", "TRISC", "TRISD", "TRISE",
            "ACCESS", "BANKED",
        ]
        for r in regs:
            self._rules.append((QRegExp(r"\b" + r + r"\b"), reg_fmt))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                self.setFormat(index, length, fmt)
                index = pattern.indexIn(text, index + length)


# ═══════════════════════════════════════════════════════════════════════════
# Line Number Area (MPLAB style)
# ═══════════════════════════════════════════════════════════════════════════

class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """Plain text editor with line numbers, current-line highlight, syntax highlighting, and inline autocomplete."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._line_number_area = LineNumberArea(self)
        self._highlighter: RasmHighlighter | None = None

        font = QFont("Courier New", 10)
        font.setFixedPitch(True)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setStyleSheet(
            f"QPlainTextEdit {{ background: {_EDITOR_BG}; color: {_EDITOR_FG}; "
            f"selection-background-color: #3399FF; selection-color: #FFFFFF; }}"
        )

        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)

        self._update_line_number_width(0)
        self._highlight_current_line()

        # ── inline autocomplete ──────────────────────────────────────────
        self._completer: QCompleter | None = None
        self._setup_completer()

    # ── completer setup ──────────────────────────────────────────────────

    def _setup_completer(self):
        """Create and configure the inline autocomplete popup."""
        self._completer = QCompleter(self)
        model = QStringListModel(_ALL_COMPLETIONS, self._completer)
        self._completer.setModel(model)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setWidget(self)
        self._completer.activated.connect(self._insert_completion)

        # Style the popup to match MPLAB theme
        popup = self._completer.popup()
        popup.setStyleSheet(
            f"QListView {{"
            f"  background: {_EDITOR_BG};"
            f"  color: {_EDITOR_FG};"
            f"  border: 1px solid #808080;"
            f"  font-family: 'Courier New';"
            f"  font-size: 10pt;"
            f"  selection-background-color: #3399FF;"
            f"  selection-color: #FFFFFF;"
            f"}}"
        )

    def _insert_completion(self, completion: str):
        """Insert the selected completion, replacing the current prefix."""
        tc = self.textCursor()
        prefix = self._text_under_cursor()
        # Remove the already-typed prefix, then insert the full word
        for _ in prefix:
            tc.deletePreviousChar()
        tc.insertText(completion)
        self.setTextCursor(tc)

    def _text_under_cursor(self) -> str:
        """Return the word fragment (including '_' and '#') currently being typed."""
        tc = self.textCursor()
        tc.movePosition(tc.StartOfBlock, tc.KeepAnchor)
        line_up_to_cursor = tc.selectedText()
        # Extract the last token: letters, digits, underscores, and '#'
        m = re.search(r'[#a-zA-Z_ščžćđŠČŽĆĐ][a-zA-Z0-9_ščžćđŠČŽĆĐ]*$', line_up_to_cursor)
        return m.group(0) if m else ""

    def keyPressEvent(self, event):
        """Handle key presses — let completer intercept when visible, then trigger it."""
        completer = self._completer

        # If the completer popup is visible, let it handle Enter/Tab/Return/Escape
        if completer and completer.popup().isVisible():
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab, Qt.Key_Escape,
                                Qt.Key_Backtab):
                event.ignore()
                return

        # Normal key processing
        super().keyPressEvent(event)

        # Don't show completer for modifier-only presses or shortcuts
        if event.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
            if completer and completer.popup().isVisible():
                completer.popup().hide()
            return

        prefix = self._text_under_cursor()

        # Need at least 2 chars to trigger the popup
        if len(prefix) < 2:
            if completer and completer.popup().isVisible():
                completer.popup().hide()
            return

        # Don't suggest inside comments (after ';')
        tc = self.textCursor()
        tc.movePosition(tc.StartOfBlock, tc.KeepAnchor)
        line_text = tc.selectedText()
        semi_pos = line_text.find(";")
        if semi_pos != -1 and len(line_text) - len(prefix) >= semi_pos:
            if completer and completer.popup().isVisible():
                completer.popup().hide()
            return

        # Update completer prefix and show popup
        completer.setCompletionPrefix(prefix)

        # Position the popup under the cursor
        cr = self.cursorRect()
        cr.setWidth(
            completer.popup().sizeHintForColumn(0)
            + completer.popup().verticalScrollBar().sizeHint().width()
            + 20
        )
        completer.complete(cr)

    def attach_highlighter(self):
        if self._highlighter is None:
            self._highlighter = RasmHighlighter(self.document())

    def line_number_area_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(cr.left(), cr.top(), self.line_number_area_width(), cr.height())

    def _highlight_current_line(self):
        extra = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor(_HIGHLIGHT_LINE))
            sel.format.setProperty(QTextCharFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extra.append(sel)
        self.setExtraSelections(extra)

    def line_number_area_paint_event(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor(_LINE_NUM_BG))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        painter.setPen(QColor(_LINE_NUM_FG))
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0, top, self._line_number_area.width() - 4,
                    self.fontMetrics().height(), Qt.AlignRight,
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1
        painter.end()


# ═══════════════════════════════════════════════════════════════════════════
# Find / Replace Bar
# ═══════════════════════════════════════════════════════════════════════════

class FindReplaceBar(QWidget):
    """Horizontal find/replace bar that sits below the tab widget."""

    def __init__(self, parent: "MplabIDE"):
        super().__init__(parent)
        self._ide = parent
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        layout.addWidget(QLabel("Find:"))
        self._find_edit = QLineEdit()
        self._find_edit.setFixedWidth(200)
        self._find_edit.returnPressed.connect(self._find_next)
        layout.addWidget(self._find_edit)

        btn_next = QPushButton("Next")
        btn_next.clicked.connect(self._find_next)
        layout.addWidget(btn_next)

        btn_prev = QPushButton("Prev")
        btn_prev.clicked.connect(self._find_prev)
        layout.addWidget(btn_prev)

        layout.addWidget(QLabel("Replace:"))
        self._replace_edit = QLineEdit()
        self._replace_edit.setFixedWidth(200)
        layout.addWidget(self._replace_edit)

        btn_replace = QPushButton("Replace")
        btn_replace.clicked.connect(self._replace)
        layout.addWidget(btn_replace)

        btn_replace_all = QPushButton("Replace All")
        btn_replace_all.clicked.connect(self._replace_all)
        layout.addWidget(btn_replace_all)

        btn_close = QPushButton("✕")
        btn_close.setFixedWidth(24)
        btn_close.clicked.connect(self.hide)
        layout.addWidget(btn_close)

        layout.addStretch()
        self.hide()

    def show_find(self):
        self.show()
        self._find_edit.setFocus()
        self._find_edit.selectAll()

    def _current_editor(self) -> CodeEditor | None:
        return self._ide.current_editor()

    def _find_next(self):
        editor = self._current_editor()
        if editor:
            editor.find(self._find_edit.text())

    def _find_prev(self):
        editor = self._current_editor()
        if editor:
            editor.find(self._find_edit.text(), QTextDocument.FindBackward)

    def _replace(self):
        editor = self._current_editor()
        if editor and editor.textCursor().hasSelection():
            editor.textCursor().insertText(self._replace_edit.text())
            self._find_next()

    def _replace_all(self):
        editor = self._current_editor()
        if not editor:
            return
        text = editor.toPlainText()
        count = text.count(self._find_edit.text())
        text = text.replace(self._find_edit.text(), self._replace_edit.text())
        editor.setPlainText(text)
        self._ide.output(f"Replaced {count} occurrence(s).")


# ═══════════════════════════════════════════════════════════════════════════
# Main IDE Window
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# Assembler Settings Dialog
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# Assembler Settings Dialog
# ═══════════════════════════════════════════════════════════════════════════

class AssemblerSettingsDialog(QDialog):
    """Dialog for configuring the Microchip PIC assembler path."""

    def __init__(self, parent=None, asm_type: str = "none", asm_path: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Assembler Settings")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)

        # ─ Assembler type group ─
        type_group = QGroupBox("Assembler")
        type_layout = QVBoxLayout(type_group)

        self._radio_mpasmx = QRadioButton("MPASM / mpasmx  (MPLAB IDE / MPLAB X bundled)")
        self._radio_pic_as = QRadioButton("pic-as  (MPLAB XC8 PIC Assembler)")
        self._radio_gpasm = QRadioButton("gpasm  (open-source gputils)")
        self._radio_none = QRadioButton("None — assembler not configured")

        type_layout.addWidget(self._radio_mpasmx)
        type_layout.addWidget(self._radio_pic_as)
        type_layout.addWidget(self._radio_gpasm)
        type_layout.addWidget(self._radio_none)
        layout.addWidget(type_group)

        # Set current selection
        radio_map = {
            "mpasmx": self._radio_mpasmx,
            "pic-as": self._radio_pic_as,
            "gpasm": self._radio_gpasm,
        }
        radio_map.get(asm_type, self._radio_none).setChecked(True)

        # ─ Path row ─
        path_group = QGroupBox("Assembler Executable Path")
        path_layout = QHBoxLayout(path_group)
        self._path_edit = QLineEdit(asm_path)
        self._path_edit.setPlaceholderText("e.g. C:\\Program Files\\Microchip\\MPLABX\\...\\mpasmx.exe")
        path_layout.addWidget(self._path_edit)
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse)
        path_layout.addWidget(btn_browse)
        btn_detect = QPushButton("Auto-Detect")
        btn_detect.clicked.connect(self._auto_detect)
        path_layout.addWidget(btn_detect)
        layout.addWidget(path_group)

        # ─ Buttons ─
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Assembler Executable", "",
            "Executables (*.exe);;All Files (*)",
        )
        if path:
            self._path_edit.setText(path)
            # Auto-select radio based on filename
            name = Path(path).name.lower()
            if "mpasmx" in name or "mpasm" in name:
                self._radio_mpasmx.setChecked(True)
            elif "pic-as" in name:
                self._radio_pic_as.setChecked(True)
            elif "gpasm" in name:
                self._radio_gpasm.setChecked(True)

    def _auto_detect(self):
        asm_type, asm_path = _auto_detect_assembler()
        if asm_type != "none":
            self._path_edit.setText(asm_path)
            radio_map = {
                "mpasmx": self._radio_mpasmx,
                "pic-as": self._radio_pic_as,
                "gpasm": self._radio_gpasm,
            }
            radio_map.get(asm_type, self._radio_none).setChecked(True)
            QMessageBox.information(self, "Found", f"Detected {asm_type}:\n{asm_path}")
        else:
            QMessageBox.warning(
                self, "Not Found",
                "No Microchip assembler found.\n\n"
                "Searched for:\n"
                "  • mpasmx.exe  (MPASM)\n"
                "  • pic-as.exe  (XC8)\n"
                "  • gpasm.exe   (gputils)\n\n"
                "Please install one or browse manually.",
            )

    def get_result(self) -> tuple[str, str]:
        """Return (asm_type, asm_path)."""
        if self._radio_mpasmx.isChecked():
            t = "mpasmx"
        elif self._radio_pic_as.isChecked():
            t = "pic-as"
        elif self._radio_gpasm.isChecked():
            t = "gpasm"
        else:
            t = "none"
        return (t, self._path_edit.text().strip())


# ═══════════════════════════════════════════════════════════════════════════
# Programmer Settings Dialog
# ═══════════════════════════════════════════════════════════════════════════

class ProgrammerSettingsDialog(QDialog):
    """Dialog for configuring the PICkit programmer tool, device, and options."""

    def __init__(self, parent=None, prog_type: str = "none", prog_path: str = "",
                 device: str = "PIC18F4550"):
        super().__init__(parent)
        self.setWindowTitle("Programmer Settings")
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)

        # ─ Programmer type ─
        type_group = QGroupBox("Programmer Tool")
        type_layout = QVBoxLayout(type_group)

        self._radio_ipecmd = QRadioButton(
            "MPLAB IPE (ipecmd)  —  PICkit 3 / PICkit 4 / MPLAB SNAP")
        self._radio_pk2cmd = QRadioButton(
            "pk2cmd  —  PICkit 2")
        self._radio_none = QRadioButton("None — programmer not configured")

        type_layout.addWidget(self._radio_ipecmd)
        type_layout.addWidget(self._radio_pk2cmd)
        type_layout.addWidget(self._radio_none)
        layout.addWidget(type_group)

        radio_map = {
            "ipecmd": self._radio_ipecmd,
            "pk2cmd": self._radio_pk2cmd,
        }
        radio_map.get(prog_type, self._radio_none).setChecked(True)

        # ─ Path ─
        path_group = QGroupBox("Programmer Executable Path")
        path_layout = QHBoxLayout(path_group)
        self._path_edit = QLineEdit(prog_path)
        self._path_edit.setPlaceholderText("e.g. C:\\Program Files\\Microchip\\MPLABX\\...\\ipecmd.exe")
        path_layout.addWidget(self._path_edit)
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse)
        path_layout.addWidget(btn_browse)
        btn_detect = QPushButton("Auto-Detect")
        btn_detect.clicked.connect(self._auto_detect)
        path_layout.addWidget(btn_detect)
        layout.addWidget(path_group)

        # ─ Device ─
        dev_group = QGroupBox("Target Device")
        dev_layout = QHBoxLayout(dev_group)
        dev_layout.addWidget(QLabel("Device:"))
        self._device_combo = QComboBox()
        self._device_combo.setEditable(True)
        self._device_combo.addItems(_PIC_DEVICES)
        idx = self._device_combo.findText(device)
        if idx >= 0:
            self._device_combo.setCurrentIndex(idx)
        else:
            self._device_combo.setEditText(device)
        self._device_combo.setMinimumWidth(200)
        dev_layout.addWidget(self._device_combo)
        dev_layout.addStretch()
        layout.addWidget(dev_group)

        # ─ Buttons ─
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Programmer Executable", "",
            "Executables (*.exe *.jar);;All Files (*)",
        )
        if path:
            self._path_edit.setText(path)
            name = Path(path).name.lower()
            if "ipecmd" in name or "ipe" in name:
                self._radio_ipecmd.setChecked(True)
            elif "pk2cmd" in name:
                self._radio_pk2cmd.setChecked(True)

    def _auto_detect(self):
        prog_type, prog_path = _auto_detect_programmer()
        if prog_type != "none":
            self._path_edit.setText(prog_path)
            radio_map = {
                "ipecmd": self._radio_ipecmd,
                "pk2cmd": self._radio_pk2cmd,
            }
            radio_map.get(prog_type, self._radio_none).setChecked(True)
            QMessageBox.information(self, "Found", f"Detected {prog_type}:\n{prog_path}")
        else:
            QMessageBox.warning(
                self, "Not Found",
                "No PICkit programmer tool found.\n\n"
                "Searched for:\n"
                "  • ipecmd.exe  (MPLAB IPE — PICkit 3/4/SNAP)\n"
                "  • pk2cmd.exe  (PICkit 2)\n\n"
                "Please install one or browse manually.",
            )

    def get_result(self) -> tuple[str, str, str]:
        """Return (prog_type, prog_path, device)."""
        if self._radio_ipecmd.isChecked():
            t = "ipecmd"
        elif self._radio_pk2cmd.isChecked():
            t = "pk2cmd"
        else:
            t = "none"
        return (t, self._path_edit.text().strip(), self._device_combo.currentText().strip())


# ═══════════════════════════════════════════════════════════════════════════
# Main IDE Window
# ═══════════════════════════════════════════════════════════════════════════

class MplabIDE(QMainWindow):
    """Main IDE window modelled after MPLAB IDE v8.92."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PIC Readable ASM IDE — MPLAB Style")
        self.resize(1200, 800)

        self._file_paths: dict[int, str] = {}  # tab index → file path
        self._modified: dict[int, bool] = {}
        self._python = self._find_python()

        # ── Assembler settings (persisted via QSettings) ──
        self._settings = QSettings("PIC-RASM", "IDE")
        self._asm_type = self._settings.value("assembler/type", "none")
        self._asm_path = self._settings.value("assembler/path", "")
        if self._asm_type == "none" or not self._asm_path:
            # Try auto-detect on first launch
            detected_type, detected_path = _auto_detect_assembler()
            if detected_type != "none":
                self._asm_type = detected_type
                self._asm_path = detected_path
                self._settings.setValue("assembler/type", self._asm_type)
                self._settings.setValue("assembler/path", self._asm_path)

        # ── Programmer settings (persisted via QSettings) ──
        self._prog_type = self._settings.value("programmer/type", "none")
        self._prog_path = self._settings.value("programmer/path", "")
        self._prog_device = self._settings.value("programmer/device", "PIC18F4550")
        if self._prog_type == "none" or not self._prog_path:
            detected_type, detected_path = _auto_detect_programmer()
            if detected_type != "none":
                self._prog_type = detected_type
                self._prog_path = detected_path
                self._settings.setValue("programmer/type", self._prog_type)
                self._settings.setValue("programmer/path", self._prog_path)

        self._init_central()
        self._init_project_tree()
        self._init_output_dock()
        self._init_menus()
        self._init_toolbar()
        self._init_statusbar()

        self._apply_global_style()

        # Open the project root in the tree
        self._set_project_root(str(_PROJECT_ROOT))

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _find_python() -> str:
        """Return path to the venv Python used by translators."""
        venv_py = _PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        if venv_py.exists():
            return str(venv_py)
        return sys.executable

    def current_editor(self) -> CodeEditor | None:
        w = self._tabs.currentWidget()
        return w if isinstance(w, CodeEditor) else None

    def output(self, text: str) -> None:
        self._output_text.appendPlainText(text)

    # ── global stylesheet (MPLAB v8.92 grey theme) ──────────────────────

    def _apply_global_style(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {_BG_COLOR};
            }}
            QMenuBar {{
                background: {_MENU_BG};
                border-bottom: 1px solid #A0A0A0;
            }}
            QMenuBar::item:selected {{
                background: #B0C4DE;
            }}
            QMenu {{
                background: {_MENU_BG};
                border: 1px solid #808080;
            }}
            QMenu::item:selected {{
                background: #3399FF;
                color: white;
            }}
            QToolBar {{
                background: {_TOOLBAR_BG};
                border: 1px solid #A0A0A0;
                spacing: 2px;
                padding: 2px;
            }}
            QToolButton {{
                background: transparent;
                border: 1px solid transparent;
                padding: 2px;
                border-radius: 2px;
            }}
            QToolButton:hover {{
                background: #B0C4DE;
                border: 1px solid #7090B0;
            }}
            QToolButton:pressed {{
                background: #90A0C0;
            }}
            QStatusBar {{
                background: {_STATUS_BG};
                border-top: 1px solid #A0A0A0;
            }}
            QTabWidget::pane {{
                border: 1px solid #A0A0A0;
            }}
            QTabBar::tab {{
                background: {_TOOLBAR_BG};
                border: 1px solid #A0A0A0;
                padding: 4px 12px;
                margin-right: 1px;
            }}
            QTabBar::tab:selected {{
                background: {_EDITOR_BG};
                border-bottom-color: {_EDITOR_BG};
            }}
            QTreeView {{
                background: {_TREE_BG};
                border: 1px solid #A0A0A0;
            }}
            QDockWidget {{
                titlebar-close-icon: none;
                titlebar-normal-icon: none;
            }}
            QDockWidget::title {{
                background: {_TOOLBAR_BG};
                border: 1px solid #A0A0A0;
                padding: 4px;
                text-align: left;
            }}
        """)

    # ── central widget (tabs + find bar) ─────────────────────────────────

    def _init_central(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

        self._find_bar = FindReplaceBar(self)
        layout.addWidget(self._find_bar)

        self.setCentralWidget(central)

    # ── project tree dock ────────────────────────────────────────────────

    def _init_project_tree(self):
        dock = QDockWidget("Project", self)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)

        self._fs_model = QFileSystemModel()
        self._fs_model.setNameFilters(["*.rasm", "*.asm", "*.json", "*.py", "*.md", "*.inc", "*.h"])
        self._fs_model.setNameFilterDisables(False)

        self._tree = QTreeView()
        self._tree.setModel(self._fs_model)
        self._tree.setHeaderHidden(True)
        # Hide Size, Type, Date columns
        for col in (1, 2, 3):
            self._tree.hideColumn(col)
        self._tree.doubleClicked.connect(self._tree_double_clicked)

        dock.setWidget(self._tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self._project_dock = dock

    def _set_project_root(self, path: str):
        idx = self._fs_model.setRootPath(path)
        self._tree.setRootIndex(idx)

    def _tree_double_clicked(self, index: QModelIndex):
        path = self._fs_model.filePath(index)
        if QFileInfo(path).isFile():
            self._open_file(path)

    # ── output dock ──────────────────────────────────────────────────────

    def _init_output_dock(self):
        dock = QDockWidget("Output", self)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)

        self._output_text = QPlainTextEdit()
        self._output_text.setReadOnly(True)
        font = QFont("Courier New", 9)
        font.setFixedPitch(True)
        self._output_text.setFont(font)
        self._output_text.setStyleSheet(
            f"background: {_OUTPUT_BG}; color: {_OUTPUT_FG};"
        )
        self._output_text.setMaximumBlockCount(5000)

        dock.setWidget(self._output_text)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self._output_dock = dock

    # ── menus (MPLAB v8.92 layout) ───────────────────────────────────────

    def _init_menus(self):
        mb = self.menuBar()

        # ── File ──
        file_menu = mb.addMenu("&File")

        act_new = file_menu.addAction("&New")
        act_new.setShortcut(QKeySequence.New)
        act_new.triggered.connect(self._new_file)

        act_open = file_menu.addAction("&Open...")
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self._open_file_dialog)

        file_menu.addSeparator()

        act_save = file_menu.addAction("&Save")
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self._save_file)

        act_save_as = file_menu.addAction("Save &As...")
        act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_save_as.triggered.connect(self._save_file_as)

        act_save_all = file_menu.addAction("Save A&ll")
        act_save_all.triggered.connect(self._save_all)

        file_menu.addSeparator()

        act_close = file_menu.addAction("&Close")
        act_close.setShortcut(QKeySequence("Ctrl+W"))
        act_close.triggered.connect(lambda: self._close_tab(self._tabs.currentIndex()))

        file_menu.addSeparator()

        act_exit = file_menu.addAction("E&xit")
        act_exit.setShortcut(QKeySequence("Alt+F4"))
        act_exit.triggered.connect(self.close)

        # ── Edit ──
        edit_menu = mb.addMenu("&Edit")

        act_undo = edit_menu.addAction("&Undo")
        act_undo.setShortcut(QKeySequence.Undo)
        act_undo.triggered.connect(lambda: self.current_editor() and self.current_editor().undo())

        act_redo = edit_menu.addAction("&Redo")
        act_redo.setShortcut(QKeySequence.Redo)
        act_redo.triggered.connect(lambda: self.current_editor() and self.current_editor().redo())

        edit_menu.addSeparator()

        act_cut = edit_menu.addAction("Cu&t")
        act_cut.setShortcut(QKeySequence.Cut)
        act_cut.triggered.connect(lambda: self.current_editor() and self.current_editor().cut())

        act_copy = edit_menu.addAction("&Copy")
        act_copy.setShortcut(QKeySequence.Copy)
        act_copy.triggered.connect(lambda: self.current_editor() and self.current_editor().copy())

        act_paste = edit_menu.addAction("&Paste")
        act_paste.setShortcut(QKeySequence.Paste)
        act_paste.triggered.connect(lambda: self.current_editor() and self.current_editor().paste())

        act_select_all = edit_menu.addAction("Select &All")
        act_select_all.setShortcut(QKeySequence.SelectAll)
        act_select_all.triggered.connect(lambda: self.current_editor() and self.current_editor().selectAll())

        edit_menu.addSeparator()

        act_find = edit_menu.addAction("&Find / Replace...")
        act_find.setShortcut(QKeySequence.Find)
        act_find.triggered.connect(self._find_bar.show_find)

        act_goto = edit_menu.addAction("&Go to Line...")
        act_goto.setShortcut(QKeySequence("Ctrl+G"))
        act_goto.triggered.connect(self._goto_line)

        # ── View ──
        view_menu = mb.addMenu("&View")

        act_project = view_menu.addAction("&Project Window")
        act_project.triggered.connect(lambda: self._project_dock.show())

        act_output = view_menu.addAction("&Output Window")
        act_output.triggered.connect(lambda: self._output_dock.show())

        view_menu.addSeparator()

        act_font = view_menu.addAction("Editor &Font...")
        act_font.triggered.connect(self._change_font)

        # ── Project ──
        project_menu = mb.addMenu("&Project")

        act_open_folder = project_menu.addAction("&Open Folder...")
        act_open_folder.triggered.connect(self._open_folder)

        # ── Tools ──
        tools_menu = mb.addMenu("&Tools")

        act_translate = tools_menu.addAction("&Build (Translate .rasm → .asm)")
        act_translate.setShortcut(QKeySequence("F7"))
        act_translate.triggered.connect(self._translate_current)

        act_reverse = tools_menu.addAction("&Reverse Translate .asm → .rasm (EN)")
        act_reverse.setShortcut(QKeySequence("Shift+F7"))
        act_reverse.triggered.connect(lambda: self._reverse_translate_current("en"))

        act_reverse_si = tools_menu.addAction("Reverse Translate .asm → .rasm (&SI)")
        act_reverse_si.triggered.connect(lambda: self._reverse_translate_current("si"))

        tools_menu.addSeparator()

        act_compile = tools_menu.addAction("&Compile .asm → .hex")
        act_compile.setShortcut(QKeySequence("F8"))
        act_compile.triggered.connect(self._compile_current)

        act_build_all = tools_menu.addAction("Build &All (.rasm → .asm → .hex)")
        act_build_all.setShortcut(QKeySequence("Ctrl+F8"))
        act_build_all.triggered.connect(self._build_and_compile_current)

        tools_menu.addSeparator()

        act_asm_settings = tools_menu.addAction("Assembler &Settings...")
        act_asm_settings.triggered.connect(self._assembler_settings)

        tools_menu.addSeparator()

        # ── Programmer ──
        prog_menu = tools_menu.addMenu("&Programmer")

        act_prog_program = prog_menu.addAction("&Program Device")
        act_prog_program.setShortcut(QKeySequence("F9"))
        act_prog_program.triggered.connect(self._program_device)

        act_prog_verify = prog_menu.addAction("&Verify")
        act_prog_verify.setShortcut(QKeySequence("Shift+F9"))
        act_prog_verify.triggered.connect(self._verify_device)

        act_prog_erase = prog_menu.addAction("&Erase Device")
        act_prog_erase.triggered.connect(self._erase_device)

        act_prog_read_id = prog_menu.addAction("Read Device &ID")
        act_prog_read_id.triggered.connect(self._read_device_id)

        prog_menu.addSeparator()

        act_prog_build_program = prog_menu.addAction("&Build All && Program")
        act_prog_build_program.setShortcut(QKeySequence("Ctrl+F9"))
        act_prog_build_program.triggered.connect(self._build_all_and_program)

        prog_menu.addSeparator()

        act_prog_settings = prog_menu.addAction("Programmer &Settings...")
        act_prog_settings.triggered.connect(self._programmer_settings)

        tools_menu.addSeparator()

        act_ref = tools_menu.addAction("Instruction &Reference")
        act_ref.setShortcut(QKeySequence("F1"))
        act_ref.triggered.connect(self._show_reference)

        # ── Help ──
        help_menu = mb.addMenu("&Help")

        act_about = help_menu.addAction("&About")
        act_about.triggered.connect(self._about)

    # ── toolbar ──────────────────────────────────────────────────────────

    def _init_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setIconSize(QSize(20, 20))
        tb.setMovable(False)

        # We use text-based toolbar buttons for portability (no external icons)
        def _add_btn(text: str, tooltip: str, callback) -> QAction:
            action = tb.addAction(text)
            action.setToolTip(tooltip)
            action.triggered.connect(callback)
            return action

        _add_btn("📄", "New File (Ctrl+N)", self._new_file)
        _add_btn("📂", "Open File (Ctrl+O)", self._open_file_dialog)
        _add_btn("💾", "Save (Ctrl+S)", self._save_file)
        tb.addSeparator()
        _add_btn("✂️", "Cut (Ctrl+X)", lambda: self.current_editor() and self.current_editor().cut())
        _add_btn("📋", "Copy (Ctrl+C)", lambda: self.current_editor() and self.current_editor().copy())
        _add_btn("📌", "Paste (Ctrl+V)", lambda: self.current_editor() and self.current_editor().paste())
        tb.addSeparator()
        _add_btn("↩", "Undo (Ctrl+Z)", lambda: self.current_editor() and self.current_editor().undo())
        _add_btn("↪", "Redo (Ctrl+Y)", lambda: self.current_editor() and self.current_editor().redo())
        tb.addSeparator()
        _add_btn("🔨", "Build — Translate (F7)", self._translate_current)
        _add_btn("🔄", "Reverse Translate (Shift+F7)", lambda: self._reverse_translate_current("en"))
        tb.addSeparator()
        _add_btn("⚙", "Compile .asm → .hex (F8)", self._compile_current)
        _add_btn("🚀", "Build All: .rasm → .asm → .hex (Ctrl+F8)", self._build_and_compile_current)
        tb.addSeparator()
        _add_btn("�", "Program Device (F9)", self._program_device)
        _add_btn("⚡", "Build All & Program (Ctrl+F9)", self._build_all_and_program)
        tb.addSeparator()
        _add_btn("�🔍", "Find / Replace (Ctrl+F)", self._find_bar.show_find)

        self.addToolBar(tb)

    # ── statusbar ────────────────────────────────────────────────────────

    def _init_statusbar(self):
        sb = self.statusBar()
        self._status_pos = QLabel("Ln 1, Col 1")
        self._status_file = QLabel("Ready")
        sb.addPermanentWidget(self._status_pos)
        sb.addWidget(self._status_file)

    def _update_status(self):
        editor = self.current_editor()
        if editor:
            cursor = editor.textCursor()
            ln = cursor.blockNumber() + 1
            col = cursor.columnNumber() + 1
            self._status_pos.setText(f"Ln {ln}, Col {col}")

    # ── tab management ───────────────────────────────────────────────────

    def _add_tab(self, editor: CodeEditor, title: str, filepath: str = "") -> int:
        idx = self._tabs.addTab(editor, title)
        self._tabs.setCurrentIndex(idx)
        self._file_paths[idx] = filepath
        self._modified[idx] = False
        editor.textChanged.connect(lambda: self._mark_modified(idx))
        editor.cursorPositionChanged.connect(self._update_status)
        editor.attach_highlighter()
        return idx

    def _mark_modified(self, idx: int):
        if not self._modified.get(idx):
            self._modified[idx] = True
            title = self._tabs.tabText(idx)
            if not title.endswith("*"):
                self._tabs.setTabText(idx, title + " *")

    def _close_tab(self, idx: int):
        if idx < 0:
            return
        if self._modified.get(idx):
            name = self._tabs.tabText(idx).rstrip(" *")
            reply = QMessageBox.question(
                self, "Save?",
                f"Save changes to {name}?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Save:
                self._save_file_at(idx)
            elif reply == QMessageBox.Cancel:
                return
        self._tabs.removeTab(idx)
        # Rebuild index maps
        new_paths = {}
        new_mod = {}
        for i in range(self._tabs.count()):
            old_idx = list(self._file_paths.keys())
            # We just re-index everything
        self._reindex_tabs()

    def _reindex_tabs(self):
        """Re-map tab indices after a tab close."""
        paths = {}
        mods = {}
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            # Find old path by widget identity
            for old_i, old_p in list(self._file_paths.items()):
                if old_i < len(self._file_paths):
                    pass  # will just rebuild
            break
        # Simpler approach: store path on the widget itself
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            fp = getattr(w, "_filepath", "")
            paths[i] = fp
            mods[i] = getattr(w, "_is_modified", False)
        self._file_paths = paths
        self._modified = mods

    def _on_tab_changed(self, idx):
        if idx >= 0:
            fp = self._file_paths.get(idx, "")
            self._status_file.setText(fp if fp else "Untitled")
            self._update_status()

    # ── file operations ──────────────────────────────────────────────────

    def _new_file(self):
        editor = CodeEditor()
        editor._filepath = ""
        editor._is_modified = False
        self._add_tab(editor, "Untitled")

    def _open_file_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open File", str(_PROJECT_ROOT),
            "Readable ASM (*.rasm);;Assembly (*.asm);;JSON (*.json);;All Files (*)",
        )
        for p in paths:
            self._open_file(p)

    def _open_file(self, filepath: str):
        # Check if already open
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if getattr(w, "_filepath", "") == filepath:
                self._tabs.setCurrentIndex(i)
                return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Cannot open file:\n{e}")
            return

        editor = CodeEditor()
        editor._filepath = filepath
        editor._is_modified = False
        editor.setPlainText(content)
        name = Path(filepath).name
        idx = self._add_tab(editor, name, filepath)
        self._modified[idx] = False
        # Reset tab title (remove the * that textChanged may have added)
        self._tabs.setTabText(idx, name)
        self.output(f"Opened: {filepath}")

    def _save_file(self):
        idx = self._tabs.currentIndex()
        if idx >= 0:
            self._save_file_at(idx)

    def _save_file_at(self, idx: int):
        editor = self._tabs.widget(idx)
        if not isinstance(editor, CodeEditor):
            return
        fp = getattr(editor, "_filepath", "")
        if not fp:
            fp, _ = QFileDialog.getSaveFileName(
                self, "Save File", str(_PROJECT_ROOT),
                "Readable ASM (*.rasm);;Assembly (*.asm);;All Files (*)",
            )
            if not fp:
                return
        try:
            with open(fp, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Cannot save file:\n{e}")
            return
        editor._filepath = fp
        editor._is_modified = False
        self._file_paths[idx] = fp
        self._modified[idx] = False
        name = Path(fp).name
        self._tabs.setTabText(idx, name)
        self.output(f"Saved: {fp}")

    def _save_file_as(self):
        idx = self._tabs.currentIndex()
        if idx < 0:
            return
        editor = self._tabs.widget(idx)
        if not isinstance(editor, CodeEditor):
            return
        fp, _ = QFileDialog.getSaveFileName(
            self, "Save File As", str(_PROJECT_ROOT),
            "Readable ASM (*.rasm);;Assembly (*.asm);;All Files (*)",
        )
        if not fp:
            return
        editor._filepath = fp
        self._save_file_at(idx)

    def _save_all(self):
        for i in range(self._tabs.count()):
            if self._modified.get(i):
                self._save_file_at(i)

    # ── edit helpers ─────────────────────────────────────────────────────

    def _goto_line(self):
        editor = self.current_editor()
        if not editor:
            return
        line, ok = QInputDialog.getInt(
            self, "Go to Line", "Line number:", 1, 1, editor.blockCount(),
        )
        if ok:
            cursor = editor.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.MoveAnchor, line - 1)
            editor.setTextCursor(cursor)
            editor.centerCursor()

    def _change_font(self):
        editor = self.current_editor()
        if not editor:
            return
        font, ok = QFontDialog.getFont(editor.font(), self, "Editor Font")
        if ok:
            for i in range(self._tabs.count()):
                w = self._tabs.widget(i)
                if isinstance(w, CodeEditor):
                    w.setFont(font)

    def _open_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Open Folder", str(_PROJECT_ROOT))
        if path:
            self._set_project_root(path)

    # ── translator integration ───────────────────────────────────────────

    def _translate_current(self):
        """Build: translate current .rasm → .asm."""
        editor = self.current_editor()
        if not editor:
            self.output("No file open.")
            return
        fp = getattr(editor, "_filepath", "")
        if not fp:
            self.output("Save the file first before building.")
            return
        if not fp.lower().endswith(".rasm"):
            self.output(f"Build expects a .rasm file, got: {fp}")
            return

        # Auto-save before build
        idx = self._tabs.currentIndex()
        self._save_file_at(idx)

        out_path = fp[:-5] + ".asm"
        self.output(f"Building: {fp} → {out_path}")
        self.output("─" * 60)

        try:
            result = subprocess.run(
                [self._python, str(_TRANSLATOR), fp, "-o", out_path],
                capture_output=True, text=True, timeout=30,
            )
            if result.stdout:
                self.output(result.stdout.strip())
            if result.stderr:
                self.output(result.stderr.strip())
            if result.returncode == 0:
                self.output("Build successful.")
            else:
                self.output(f"Build failed (exit code {result.returncode}).")
        except Exception as e:
            self.output(f"Build error: {e}")
        self.output("")

    def _reverse_translate_current(self, lang: str = "en"):
        """Reverse translate current .asm → .rasm."""
        editor = self.current_editor()
        if not editor:
            self.output("No file open.")
            return
        fp = getattr(editor, "_filepath", "")
        if not fp:
            self.output("Save the file first.")
            return
        if not fp.lower().endswith(".asm"):
            self.output(f"Reverse translate expects a .asm file, got: {fp}")
            return

        idx = self._tabs.currentIndex()
        self._save_file_at(idx)

        out_path = fp[:-4] + ".rasm"
        self.output(f"Reverse translating ({lang}): {fp} → {out_path}")
        self.output("─" * 60)

        try:
            result = subprocess.run(
                [self._python, str(_REVERSE_TRANSLATOR), fp, "-o", out_path, "--lang", lang],
                capture_output=True, text=True, timeout=30,
            )
            if result.stdout:
                self.output(result.stdout.strip())
            if result.stderr:
                self.output(result.stderr.strip())
            if result.returncode == 0:
                self.output("Reverse translation successful.")
                self._open_file(out_path)
            else:
                self.output(f"Reverse translation failed (exit code {result.returncode}).")
        except Exception as e:
            self.output(f"Error: {e}")
        self.output("")

    # ── assembler (compile .asm → .hex) ───────────────────────────────

    def _assembler_settings(self):
        """Open the assembler settings dialog."""
        dlg = AssemblerSettingsDialog(self, self._asm_type, self._asm_path)
        if dlg.exec_() == QDialog.Accepted:
            self._asm_type, self._asm_path = dlg.get_result()
            self._settings.setValue("assembler/type", self._asm_type)
            self._settings.setValue("assembler/path", self._asm_path)
            if self._asm_type != "none" and self._asm_path:
                self.output(f"Assembler set: {self._asm_type} → {self._asm_path}")
            else:
                self.output("Assembler: not configured.")

    def _check_assembler(self) -> bool:
        """Verify that an assembler is configured. Prompt settings if not."""
        if self._asm_type == "none" or not self._asm_path:
            reply = QMessageBox.question(
                self, "Assembler Not Configured",
                "No Microchip PIC assembler is configured.\n\n"
                "Would you like to configure it now?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._assembler_settings()
            return self._asm_type != "none" and bool(self._asm_path)
        if not Path(self._asm_path).exists():
            self.output(f"ERROR: Assembler not found at: {self._asm_path}")
            self.output("Go to Tools → Assembler Settings to fix the path.")
            return False
        return True

    def _build_asm_command(self, asm_file: str) -> list[str]:
        """Build the command line for the configured assembler."""
        asm_dir = str(Path(asm_file).parent)
        asm_name = Path(asm_file).name

        if self._asm_type == "mpasmx":
            # MPASM: mpasmx.exe /q /o- /l- <file.asm>
            #   /q  = quiet
            #   /o- = no object file (just hex)
            #   /l- = no listing file
            return [self._asm_path, "/q", asm_name]

        elif self._asm_type == "pic-as":
            # XC8 pic-as: pic-as -o output.hex <file.asm>
            hex_name = Path(asm_file).stem + ".hex"
            return [self._asm_path, "-mcpu=PIC18F4550", "-o", hex_name, asm_name]

        elif self._asm_type == "gpasm":
            # gputils: gpasm -o file.hex file.asm
            hex_name = Path(asm_file).stem + ".hex"
            return [self._asm_path, "-o", hex_name, asm_name]

        return []

    def _compile_asm_file(self, asm_file: str) -> bool:
        """Compile the given .asm file to .hex. Returns True on success."""
        if not self._check_assembler():
            return False

        cmd = self._build_asm_command(asm_file)
        if not cmd:
            self.output("ERROR: Unknown assembler type.")
            return False

        asm_dir = str(Path(asm_file).parent)
        self.output(f"Assembler: {self._asm_type}")
        self.output(f"Command:   {' '.join(cmd)}")
        self.output(f"Directory: {asm_dir}")
        self.output("─" * 60)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
                cwd=asm_dir,
            )
            if result.stdout:
                self.output(result.stdout.strip())
            if result.stderr:
                self.output(result.stderr.strip())
            if result.returncode == 0:
                hex_file = Path(asm_file).with_suffix(".hex")
                # Check for generated .hex (MPASM may name it differently)
                err_file = Path(asm_file).with_suffix(".err")
                if hex_file.exists():
                    size = hex_file.stat().st_size
                    self.output(f"Compile successful: {hex_file.name} ({size} bytes)")
                else:
                    self.output("Compile finished (exit code 0).")
                # Show .err file contents if present (MPASM writes errors there)
                if err_file.exists():
                    err_text = err_file.read_text(encoding="utf-8", errors="replace").strip()
                    if err_text:
                        self.output("\n── Assembler Messages ──")
                        self.output(err_text)
                return True
            else:
                self.output(f"Compile FAILED (exit code {result.returncode}).")
                # Show .err file if present
                err_file = Path(asm_file).with_suffix(".err")
                if err_file.exists():
                    err_text = err_file.read_text(encoding="utf-8", errors="replace").strip()
                    if err_text:
                        self.output("\n── Assembler Errors ──")
                        self.output(err_text)
                return False
        except FileNotFoundError:
            self.output(f"ERROR: Assembler executable not found: {self._asm_path}")
            self.output("Go to Tools → Assembler Settings to fix the path.")
            return False
        except subprocess.TimeoutExpired:
            self.output("ERROR: Assembler timed out (60 s).")
            return False
        except Exception as e:
            self.output(f"Compile error: {e}")
            return False

    def _compile_current(self):
        """Compile current .asm file → .hex using the configured Microchip assembler."""
        editor = self.current_editor()
        if not editor:
            self.output("No file open.")
            return
        fp = getattr(editor, "_filepath", "")
        if not fp:
            self.output("Save the file first.")
            return
        if not fp.lower().endswith(".asm"):
            self.output(f"Compile expects a .asm file, got: {fp}")
            return

        idx = self._tabs.currentIndex()
        self._save_file_at(idx)

        self.output(f"Compiling: {fp}")
        self.output("═" * 60)
        self._compile_asm_file(fp)
        self.output("")

    def _build_and_compile_current(self):
        """Full pipeline: .rasm → .asm → .hex."""
        editor = self.current_editor()
        if not editor:
            self.output("No file open.")
            return
        fp = getattr(editor, "_filepath", "")
        if not fp:
            self.output("Save the file first.")
            return

        # Determine the starting file type
        if fp.lower().endswith(".rasm"):
            # Step 1: translate .rasm → .asm
            idx = self._tabs.currentIndex()
            self._save_file_at(idx)

            asm_path = fp[:-5] + ".asm"
            self.output("═" * 60)
            self.output("  FULL BUILD: .rasm → .asm → .hex")
            self.output("═" * 60)
            self.output(f"\nStep 1: Translate {Path(fp).name} → {Path(asm_path).name}")
            self.output("─" * 60)

            try:
                result = subprocess.run(
                    [self._python, str(_TRANSLATOR), fp, "-o", asm_path],
                    capture_output=True, text=True, timeout=30,
                )
                if result.stdout:
                    self.output(result.stdout.strip())
                if result.stderr:
                    self.output(result.stderr.strip())
                if result.returncode != 0:
                    self.output(f"Translation failed (exit code {result.returncode}). Aborting.")
                    self.output("")
                    return
                self.output("Translation successful.")
            except Exception as e:
                self.output(f"Translation error: {e}")
                self.output("")
                return

            # Step 2: compile .asm → .hex
            self.output(f"\nStep 2: Compile {Path(asm_path).name} → {Path(asm_path).stem}.hex")
            self.output("─" * 60)
            self._compile_asm_file(asm_path)
            self.output("")

        elif fp.lower().endswith(".asm"):
            # Just compile
            self._compile_current()
        else:
            self.output(f"Build All expects a .rasm or .asm file, got: {fp}")

    def _show_reference(self):
        """Show instruction reference in output."""
        self.output("=" * 60)
        self.output("  INSTRUCTION REFERENCE")
        self.output("=" * 60)
        try:
            result = subprocess.run(
                [self._python, str(_TRANSLATOR), "--ref"],
                capture_output=True, text=True, timeout=15,
            )
            if result.stdout:
                self.output(result.stdout)
            if result.stderr:
                self.output(result.stderr)
        except Exception as e:
            self.output(f"Error: {e}")
        self.output("")

    # ── programmer (PICkit) integration ───────────────────────────────────

    def _programmer_settings(self):
        """Open the programmer settings dialog."""
        dlg = ProgrammerSettingsDialog(
            self, self._prog_type, self._prog_path, self._prog_device)
        if dlg.exec_() == QDialog.Accepted:
            self._prog_type, self._prog_path, self._prog_device = dlg.get_result()
            self._settings.setValue("programmer/type", self._prog_type)
            self._settings.setValue("programmer/path", self._prog_path)
            self._settings.setValue("programmer/device", self._prog_device)
            if self._prog_type != "none" and self._prog_path:
                self.output(
                    f"Programmer set: {self._prog_type} → {self._prog_path}  "
                    f"Device: {self._prog_device}")
            else:
                self.output("Programmer: not configured.")

    def _check_programmer(self) -> bool:
        """Verify that a programmer is configured. Prompt settings if not."""
        if self._prog_type == "none" or not self._prog_path:
            reply = QMessageBox.question(
                self, "Programmer Not Configured",
                "No PICkit programmer is configured.\n\n"
                "Would you like to configure it now?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._programmer_settings()
            return self._prog_type != "none" and bool(self._prog_path)
        if not Path(self._prog_path).exists():
            self.output(f"ERROR: Programmer tool not found at: {self._prog_path}")
            self.output("Go to Tools → Programmer → Programmer Settings to fix the path.")
            return False
        return True

    def _run_programmer_cmd(self, cmd: list[str], action_label: str,
                            cwd: str | None = None) -> bool:
        """Run a programmer command and display output. Returns True on success."""
        self.output(f"Programmer: {self._prog_type}  |  Device: {self._prog_device}")
        self.output(f"Action:     {action_label}")
        self.output(f"Command:    {' '.join(cmd)}")
        self.output("─" * 60)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
                cwd=cwd,
            )
            if result.stdout:
                self.output(result.stdout.strip())
            if result.stderr:
                self.output(result.stderr.strip())
            if result.returncode == 0:
                self.output(f"{action_label} completed successfully.")
                return True
            else:
                self.output(f"{action_label} FAILED (exit code {result.returncode}).")
                return False
        except FileNotFoundError:
            self.output(f"ERROR: Programmer executable not found: {self._prog_path}")
            self.output("Go to Tools → Programmer → Programmer Settings.")
            return False
        except subprocess.TimeoutExpired:
            self.output(f"ERROR: {action_label} timed out (120 s).")
            return False
        except Exception as e:
            self.output(f"{action_label} error: {e}")
            return False

    def _find_hex_for_current(self) -> str | None:
        """Find the .hex file corresponding to the current editor file."""
        editor = self.current_editor()
        if not editor:
            self.output("No file open.")
            return None
        fp = getattr(editor, "_filepath", "")
        if not fp:
            self.output("Save the file first.")
            return None

        # Determine hex path
        if fp.lower().endswith(".hex"):
            return fp
        elif fp.lower().endswith(".asm"):
            hex_path = fp[:-4] + ".hex"
        elif fp.lower().endswith(".rasm"):
            hex_path = fp[:-5] + ".hex"
        else:
            hex_path = fp + ".hex"

        if not Path(hex_path).exists():
            self.output(f"HEX file not found: {hex_path}")
            self.output("Build the project first (F8 or Ctrl+F8).")
            return None
        return hex_path

    def _program_device(self):
        """Program the target device with the .hex file."""
        if not self._check_programmer():
            return
        hex_path = self._find_hex_for_current()
        if not hex_path:
            return

        self.output("═" * 60)
        self.output("  PROGRAMMING DEVICE")
        self.output("═" * 60)

        cwd = str(Path(hex_path).parent)

        if self._prog_type == "pk2cmd":
            cmd = [
                self._prog_path,
                "-P" + self._prog_device,
                "-F" + hex_path,
                "-M",   # program
                "-J",   # power target from PICkit (5V)
            ]
        elif self._prog_type == "ipecmd":
            cmd = [
                self._prog_path,
                "-P" + self._prog_device,
                "-TPPK3",   # tool = PICkit 3 (also works for PICkit 4 / SNAP)
                "-F" + hex_path,
                "-M",       # program
                "-W",       # power target from programmer
            ]
        else:
            self.output("ERROR: Unknown programmer type.")
            return

        self._run_programmer_cmd(cmd, "Program", cwd)
        self.output("")

    def _verify_device(self):
        """Verify the target device against the .hex file."""
        if not self._check_programmer():
            return
        hex_path = self._find_hex_for_current()
        if not hex_path:
            return

        self.output("═" * 60)
        self.output("  VERIFYING DEVICE")
        self.output("═" * 60)

        cwd = str(Path(hex_path).parent)

        if self._prog_type == "pk2cmd":
            cmd = [
                self._prog_path,
                "-P" + self._prog_device,
                "-F" + hex_path,
                "-Y",   # verify
                "-J",
            ]
        elif self._prog_type == "ipecmd":
            cmd = [
                self._prog_path,
                "-P" + self._prog_device,
                "-TPPK3",
                "-F" + hex_path,
                "-Y",   # verify
                "-W",
            ]
        else:
            self.output("ERROR: Unknown programmer type.")
            return

        self._run_programmer_cmd(cmd, "Verify", cwd)
        self.output("")

    def _erase_device(self):
        """Erase the target device (bulk erase)."""
        if not self._check_programmer():
            return

        reply = QMessageBox.question(
            self, "Erase Device",
            f"This will perform a BULK ERASE on {self._prog_device}.\n\n"
            "All program memory, data EEPROM, and configuration bits will be erased.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.output("═" * 60)
        self.output("  ERASING DEVICE")
        self.output("═" * 60)

        if self._prog_type == "pk2cmd":
            cmd = [
                self._prog_path,
                "-P" + self._prog_device,
                "-E",   # erase
                "-J",
            ]
        elif self._prog_type == "ipecmd":
            cmd = [
                self._prog_path,
                "-P" + self._prog_device,
                "-TPPK3",
                "-E",   # erase
                "-W",
            ]
        else:
            self.output("ERROR: Unknown programmer type.")
            return

        self._run_programmer_cmd(cmd, "Erase")
        self.output("")

    def _read_device_id(self):
        """Read and display the target device ID."""
        if not self._check_programmer():
            return

        self.output("═" * 60)
        self.output("  READING DEVICE ID")
        self.output("═" * 60)

        if self._prog_type == "pk2cmd":
            cmd = [
                self._prog_path,
                "-P" + self._prog_device,
                "-I",   # read device ID
                "-J",
            ]
        elif self._prog_type == "ipecmd":
            # ipecmd doesn't have a direct "read ID" flag;
            # we connect and the ID is printed automatically
            cmd = [
                self._prog_path,
                "-P" + self._prog_device,
                "-TPPK3",
                "-W",
            ]
        else:
            self.output("ERROR: Unknown programmer type.")
            return

        self._run_programmer_cmd(cmd, "Read Device ID")
        self.output("")

    def _build_all_and_program(self):
        """Full pipeline: .rasm → .asm → .hex → Program device."""
        editor = self.current_editor()
        if not editor:
            self.output("No file open.")
            return
        fp = getattr(editor, "_filepath", "")
        if not fp:
            self.output("Save the file first.")
            return

        # Step 1 + 2: Build (translate + compile)
        if fp.lower().endswith(".rasm"):
            idx = self._tabs.currentIndex()
            self._save_file_at(idx)

            asm_path = fp[:-5] + ".asm"
            hex_path = fp[:-5] + ".hex"

            self.output("═" * 60)
            self.output("  FULL BUILD & PROGRAM: .rasm → .asm → .hex → Device")
            self.output("═" * 60)

            # Step 1: translate
            self.output(f"\nStep 1: Translate {Path(fp).name} → {Path(asm_path).name}")
            self.output("─" * 60)
            try:
                result = subprocess.run(
                    [self._python, str(_TRANSLATOR), fp, "-o", asm_path],
                    capture_output=True, text=True, timeout=30,
                )
                if result.stdout:
                    self.output(result.stdout.strip())
                if result.stderr:
                    self.output(result.stderr.strip())
                if result.returncode != 0:
                    self.output(f"Translation failed (exit code {result.returncode}). Aborting.")
                    self.output("")
                    return
                self.output("Translation successful.")
            except Exception as e:
                self.output(f"Translation error: {e}")
                self.output("")
                return

            # Step 2: compile
            self.output(f"\nStep 2: Compile {Path(asm_path).name} → {Path(asm_path).stem}.hex")
            self.output("─" * 60)
            if not self._compile_asm_file(asm_path):
                self.output("Compile failed. Aborting.")
                self.output("")
                return

        elif fp.lower().endswith(".asm"):
            idx = self._tabs.currentIndex()
            self._save_file_at(idx)
            hex_path = fp[:-4] + ".hex"

            self.output("═" * 60)
            self.output("  BUILD & PROGRAM: .asm → .hex → Device")
            self.output("═" * 60)

            self.output(f"\nStep 1: Compile {Path(fp).name} → {Path(fp).stem}.hex")
            self.output("─" * 60)
            if not self._compile_asm_file(fp):
                self.output("Compile failed. Aborting.")
                self.output("")
                return
        else:
            self.output(f"Build & Program expects a .rasm or .asm file, got: {fp}")
            return

        # Step 3: program
        if not Path(hex_path).exists():
            self.output(f"\nHEX file not found: {hex_path}")
            self.output("Aborting programming step.")
            self.output("")
            return

        if not self._check_programmer():
            self.output("Programmer not configured. Skipping programming step.")
            self.output("")
            return

        step_n = "Step 3" if fp.lower().endswith(".rasm") else "Step 2"
        self.output(f"\n{step_n}: Program {Path(hex_path).name} → {self._prog_device}")
        self.output("─" * 60)

        cwd = str(Path(hex_path).parent)
        if self._prog_type == "pk2cmd":
            cmd = [
                self._prog_path,
                "-P" + self._prog_device,
                "-F" + hex_path,
                "-M",
                "-J",
            ]
        elif self._prog_type == "ipecmd":
            cmd = [
                self._prog_path,
                "-P" + self._prog_device,
                "-TPPK3",
                "-F" + hex_path,
                "-M",
                "-W",
            ]
        else:
            self.output("ERROR: Unknown programmer type.")
            self.output("")
            return

        self._run_programmer_cmd(cmd, "Program", cwd)
        self.output("")

    # ── about ────────────────────────────────────────────────────────────

    def _about(self):
        QMessageBox.about(
            self,
            "About PIC Readable ASM IDE",
            "<h2>PIC Readable ASM IDE</h2>"
            "<p>MPLAB v8.92 style IDE for PIC16/PIC18 readable assembly.</p>"
            "<p>Features:</p>"
            "<ul>"
            "<li>Syntax highlighting for .rasm / .asm files</li>"
            "<li>Integrated forward &amp; reverse translator</li>"
            "<li>Compile to .hex via Microchip MPASM / pic-as / gpasm</li>"
            "<li>Full pipeline: .rasm → .asm → .hex</li>"
            "<li>PICkit programming: program, verify, erase, read ID</li>"
            "<li>Project tree, find/replace, line numbers</li>"
            "</ul>"
            f"<p><b>Assembler:</b> {self._asm_type} — <code>{self._asm_path or 'not configured'}</code></p>"
            f"<p><b>Programmer:</b> {self._prog_type} — <code>{self._prog_path or 'not configured'}</code></p>"
            f"<p><b>Device:</b> {self._prog_device}</p>"
            "<p>Built with PyQt5.</p>",
        )

    # ── close event ──────────────────────────────────────────────────────

    def closeEvent(self, event):
        for i in range(self._tabs.count()):
            if self._modified.get(i):
                name = self._tabs.tabText(i).rstrip(" *")
                reply = QMessageBox.question(
                    self, "Save?",
                    f"Save changes to {name}?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                )
                if reply == QMessageBox.Save:
                    self._save_file_at(i)
                elif reply == QMessageBox.Cancel:
                    event.ignore()
                    return
        event.accept()


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PIC Readable ASM IDE")
    app.setStyle("Fusion")

    # Set Fusion palette to look like MPLAB v8.92
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(_BG_COLOR))
    palette.setColor(QPalette.WindowText, QColor("#000000"))
    palette.setColor(QPalette.Base, QColor(_EDITOR_BG))
    palette.setColor(QPalette.AlternateBase, QColor(_BG_COLOR))
    palette.setColor(QPalette.ToolTipBase, QColor("#FFFFDC"))
    palette.setColor(QPalette.ToolTipText, QColor("#000000"))
    palette.setColor(QPalette.Text, QColor("#000000"))
    palette.setColor(QPalette.Button, QColor(_TOOLBAR_BG))
    palette.setColor(QPalette.ButtonText, QColor("#000000"))
    palette.setColor(QPalette.Highlight, QColor("#3399FF"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)

    window = MplabIDE()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
