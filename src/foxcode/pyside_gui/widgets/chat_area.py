from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QFrame, QSpacerItem,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor

from foxcode.pyside_gui.theme import (
    BG_PRIMARY, BG_SECONDARY, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT, USER_MSG_BG,
)


class MessageBubble(QFrame):
    """A single chat message bubble."""

    def __init__(self, text: str, is_user: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self.is_user = is_user
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        if is_user:
            bg = USER_MSG_BG
            border_css = "border: 1px solid #D6E4F0;"
            align = "right"
        else:
            bg = BG_PRIMARY
            border_css = f"border: 1px solid {BORDER};"
            align = "left"

        self.setStyleSheet(f"""
            MessageBubble {{
                background-color: {bg};
                {border_css}
                border-radius: 12px;
                padding: 0px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # Role label
        role = "You" if is_user else "FoxCode"
        role_label = QLabel(role)
        role_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        role_label.setStyleSheet(f"""
            color: {ACCENT if not is_user else TEXT_SECONDARY};
            background: transparent;
            border: none;
            padding: 0;
        """)
        layout.addWidget(role_label)

        # Message text
        msg_label = QLabel(text)
        msg_label.setFont(QFont("Segoe UI", 13))
        msg_label.setWordWrap(True)
        msg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg_label.setStyleSheet(f"""
            color: {TEXT_PRIMARY};
            background: transparent;
            border: none;
            padding: 0;
            line-height: 1.5;
        """)
        layout.addWidget(msg_label)

        self.setMaximumWidth(640)


class ChatArea(QWidget):
    """Scrollable chat message display area."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BG_PRIMARY};")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: {BG_PRIMARY};
            }}
        """)

        self._container = QWidget()
        self._container.setStyleSheet(f"background: {BG_PRIMARY};")
        self._messages_layout = QVBoxLayout(self._container)
        self._messages_layout.setContentsMargins(32, 24, 32, 24)
        self._messages_layout.setSpacing(16)
        self._messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll.setWidget(self._container)
        outer_layout.addWidget(self._scroll)

        # Add demo messages
        self._add_demo_messages()

    def _add_demo_messages(self):
        demos = [
            (True, "Can you help me refactor the authentication module? I want to split it into separate concerns."),
            (False, "I'd be happy to help refactor the authentication module. Let me analyze the current structure first.\n\nHere's what I suggest:\n\n1. Extract token management into a dedicated TokenService\n2. Move password hashing to a CryptoUtils module\n3. Create an AuthMiddleware for request validation\n4. Keep the main AuthController as a thin orchestration layer\n\nShall I start with any specific part?"),
            (True, "Let's start with the TokenService. What would that look like?"),
            (False, "Here's a clean TokenService implementation:\n\nThe service would handle JWT creation, validation, refresh logic, and token blacklisting. It encapsulates all token-related operations behind a simple interface so the rest of your auth system doesn't need to know about JWT internals.\n\nKey methods:\n\u2022 generate(payload) \u2192 creates a signed token\n\u2022 verify(token) \u2192 validates and decodes\n\u2022 refresh(token) \u2192 issues a new token\n\u2022 revoke(token) \u2192 adds to blacklist\n\nWould you like me to write the full implementation?"),
        ]
        for is_user, text in demos:
            self.add_message(text, is_user)

    def add_message(self, text: str, is_user: bool):
        row = QHBoxLayout()
        row.setSpacing(0)

        bubble = MessageBubble(text, is_user)

        if is_user:
            row.addStretch()
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch()

        self._messages_layout.addLayout(row)

        # Scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        vbar = self._scroll.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    def clear_messages(self):
        while self._messages_layout.count():
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
