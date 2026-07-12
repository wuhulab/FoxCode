from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QCursor

from foxcode.pyside_gui.theme import (
    BG_PRIMARY, BG_SECONDARY, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT, ACCENT_HOVER, HOVER,
)


class SessionItem(QFrame):
    """A single conversation session entry."""

    clicked = Signal(int)

    def __init__(self, index: int, title: str, preview: str, timestamp: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.index = index
        self._active = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(68)
        self.setStyleSheet(self._build_style(False, False))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        # Title row
        top_row = QHBoxLayout()
        top_row.setSpacing(0)
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        title_label.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        top_row.addWidget(title_label)
        top_row.addStretch()
        ts_label = QLabel(timestamp)
        ts_label.setFont(QFont("Segoe UI", 10))
        ts_label.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        top_row.addWidget(ts_label)
        layout.addLayout(top_row)

        # Preview
        preview_label = QLabel(preview)
        preview_label.setFont(QFont("Segoe UI", 11))
        preview_label.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        preview_label.setMaximumWidth(220)
        preview_label.setWordWrap(False)
        layout.addWidget(preview_label)

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool):
        self._active = value
        self.setStyleSheet(self._build_style(value, False))

    def _build_style(self, active: bool, hovered: bool) -> str:
        if active:
            bg = HOVER
            border_left = f"3px solid {ACCENT}"
        elif hovered:
            bg = BG_SECONDARY
            border_left = "3px solid transparent"
        else:
            bg = BG_PRIMARY
            border_left = "3px solid transparent"
        return f"""
            SessionItem {{
                background-color: {bg};
                border: none;
                border-left: {border_left};
                border-bottom: 1px solid {BORDER};
                border-radius: 0px;
            }}
        """

    def enterEvent(self, event):
        if not self._active:
            self.setStyleSheet(self._build_style(False, True))

    def leaveEvent(self, event):
        if not self._active:
            self.setStyleSheet(self._build_style(False, False))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)


class SessionPanel(QWidget):
    """Left sidebar showing conversation/session list."""

    session_selected = Signal(int)
    new_chat_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setStyleSheet(f"""
            SessionPanel {{
                background-color: {BG_PRIMARY};
                border-right: 1px solid {BORDER};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # New chat button
        new_chat_btn = QPushButton("\u2795  New Chat")
        new_chat_btn.setFixedHeight(44)
        new_chat_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        new_chat_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        new_chat_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BG_PRIMARY};
                color: {ACCENT};
                border: none;
                border-bottom: 1px solid {BORDER};
                text-align: left;
                padding-left: 16px;
            }}
            QPushButton:hover {{
                background-color: {BG_SECONDARY};
            }}
        """)
        new_chat_btn.clicked.connect(self.new_chat_requested.emit)
        main_layout.addWidget(new_chat_btn)

        # Scroll area for sessions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_PRIMARY}; }}")

        container = QWidget()
        self._items_layout = QVBoxLayout(container)
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(0)
        self._items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        self._items: list[SessionItem] = []
        self._active_index = -1

        # Demo sessions
        demos = [
            ("Refactor auth module", "Let's restructure the authentication...", "2m ago"),
            ("Fix build errors", "The TypeScript compiler is throwing...", "1h ago"),
            ("Add dark mode", "I need to implement a dark mode toggle...", "3h ago"),
            ("API design review", "Can you review the REST API endpoints...", "Yesterday"),
            ("Database migration", "We need to migrate from SQLite to...", "2d ago"),
        ]
        for i, (title, preview, ts) in enumerate(demos):
            self.add_session(title, preview, ts)

        if self._items:
            self._set_active(0)

    def add_session(self, title: str, preview: str, timestamp: str):
        index = len(self._items)
        item = SessionItem(index, title, preview, timestamp)
        item.clicked.connect(self._on_item_clicked)
        self._items.append(item)
        self._items_layout.addWidget(item)

    def _on_item_clicked(self, index: int):
        self._set_active(index)
        self.session_selected.emit(index)

    def _set_active(self, index: int):
        self._active_index = index
        for item in self._items:
            item.active = item.index == index
