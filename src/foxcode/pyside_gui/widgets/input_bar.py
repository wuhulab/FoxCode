from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QTextEdit, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QFont, QCursor, QKeyEvent

from foxcode.pyside_gui.theme import (
    BG_PRIMARY, BG_SECONDARY, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT, ACCENT_HOVER, HOVER,
)


class ChatInput(QTextEdit):
    """Auto-growing text input that sends on Enter (Shift+Enter for newline)."""

    submit_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setPlaceholderText("输入消息… (Enter 发送, Shift+Enter 换行)")
        self.setFont(QFont("Segoe UI", 13))
        self.setAcceptRichText(False)
        self.setMinimumHeight(40)
        self.setMaximumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet(f"""
            ChatInput {{
                background-color: {BG_PRIMARY};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 12px;
                padding: 8px 14px;
                selection-background-color: {ACCENT};
                selection-color: #FFFFFF;
            }}
            ChatInput:focus {{
                border: 1.5px solid {ACCENT};
            }}
        """)
        self.document().contentsChanged.connect(self._adjust_height)

    def _adjust_height(self):
        doc_height = int(self.document().size().height()) + 16
        new_height = max(40, min(doc_height, 160))
        self.setFixedHeight(new_height)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submit_requested.emit()
                return
        else:
            super().keyPressEvent(event)


class InputBar(QWidget):
    """Bottom input bar with text field and send button."""

    message_submitted = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            InputBar {{
                background-color: {BG_SECONDARY};
                border-top: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(12)

        self._input = ChatInput()
        self._input.submit_requested.connect(self._on_submit)
        layout.addWidget(self._input)

        self._send_btn = QPushButton("发送")
        self._send_btn.setFixedSize(72, 40)
        self._send_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._send_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: #0A7A5E;
            }}
            QPushButton:disabled {{
                background-color: {BORDER};
                color: {TEXT_SECONDARY};
            }}
        """)
        self._send_btn.clicked.connect(self._on_submit)
        layout.addWidget(self._send_btn)

    def _on_submit(self):
        text = self._input.toPlainText().strip()
        if text:
            self.message_submitted.emit(text)
            self._input.clear()

    def set_enabled(self, enabled: bool):
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)

    def focus_input(self):
        self._input.setFocus()
