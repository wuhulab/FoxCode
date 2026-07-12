from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor

from foxcode.pyside_gui.theme import (
    BG_PRIMARY, BG_SECONDARY, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT, HOVER,
)


class Toolbar(QWidget):
    """Top toolbar showing model name, project path, and window controls."""

    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()
    settings_clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            Toolbar {{
                background-color: {BG_PRIMARY};
                border-bottom: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(12)

        # Model indicator
        model_dot = QLabel("\u25CF")
        model_dot.setStyleSheet(f"color: {ACCENT}; font-size: 10px; background: transparent;")
        model_dot.setFixedWidth(14)
        layout.addWidget(model_dot)

        model_label = QLabel("claude-opus-4-7")
        model_label.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        model_label.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(model_label)

        # Separator
        sep = QLabel("\u2502")
        sep.setStyleSheet(f"color: {BORDER}; background: transparent;")
        layout.addWidget(sep)

        # Project path
        path_label = QLabel("S:\\shunxcode\\src\\foxcode")
        path_label.setFont(QFont("Segoe UI", 11))
        path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        layout.addWidget(path_label)

        layout.addStretch()

        # Settings button
        settings_btn = QPushButton("\u2699")
        settings_btn.setFixedSize(32, 32)
        settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        settings_btn.setFont(QFont("Segoe UI", 16))
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_SECONDARY};
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {HOVER};
                color: {TEXT_PRIMARY};
            }}
        """)
        settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(settings_btn)

        # Spacer before window controls
        layout.addSpacing(8)

        # Window controls
        for symbol, signal, hover_color in [
            ("\u2013", self.minimize_clicked, HOVER),
            ("\u25A1", self.maximize_clicked, HOVER),
            ("\u2715", self.close_clicked, "#E81123"),
        ]:
            btn = QPushButton(symbol)
            btn.setFixedSize(36, 28)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFont(QFont("Segoe UI", 11))
            text_hover = "#FFFFFF" if hover_color == "#E81123" else TEXT_PRIMARY
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {TEXT_SECONDARY};
                    border: none;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                    color: {text_hover};
                }}
            """)
            btn.clicked.connect(signal.emit)
            layout.addWidget(btn)

    def mousePressEvent(self, event):
        """Allow dragging the window from the toolbar."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_pos') and event.buttons() & Qt.MouseButton.LeftButton:
            window = self.window()
            delta = event.globalPosition().toPoint() - self._drag_pos
            window.move(window.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()
