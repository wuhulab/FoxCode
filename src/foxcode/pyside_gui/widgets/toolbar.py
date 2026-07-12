from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QCursor

from foxcode.pyside_gui.theme import (
    BG_PRIMARY, BG_SECONDARY, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT, HOVER,
)
from foxcode.pyside_gui.icons import (
    icon_settings, icon_minimize, icon_maximize, icon_close, icon_model_dot,
)


class Toolbar(QWidget):
    """Top toolbar showing model name, project path, and window controls."""

    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()
    settings_clicked = Signal()

    def __init__(
        self,
        model_name: str = "claude-opus-4-7",
        project_path: str = "S:\\shunxcode\\src\\foxcode",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(
            f"Toolbar {{ background-color: {BG_PRIMARY}; border-bottom: 1px solid {BORDER}; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(12)

        # Model indicator (SVG dot)
        self._model_dot = QLabel()
        self._model_dot.setPixmap(icon_model_dot(ACCENT, 10))
        self._model_dot.setFixedWidth(14)
        self._model_dot.setStyleSheet("background: transparent;")
        layout.addWidget(self._model_dot)

        # Model label
        self._model_label = QLabel(model_name)
        self._model_label.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._model_label.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(self._model_label)

        # Separator (thin vertical line widget instead of unicode)
        sep = QWidget()
        sep.setFixedSize(1, 20)
        sep.setStyleSheet(f"background-color: {BORDER};")
        layout.addWidget(sep)

        # Project path
        self._path_label = QLabel(project_path)
        self._path_label.setFont(QFont("Segoe UI", 11))
        self._path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        layout.addWidget(self._path_label)

        layout.addStretch()

        # Settings button (SVG icon)
        settings_btn = QPushButton()
        settings_btn.setIcon(icon_settings(TEXT_SECONDARY, 18))
        settings_btn.setIconSize(QSize(18, 18))
        settings_btn.setFixedSize(32, 32)
        settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        settings_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 6px; }"
            f" QPushButton:hover {{ background-color: {HOVER}; }}"
        )
        settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(settings_btn)

        # Spacer before window controls
        layout.addSpacing(8)

        # Window controls (SVG icons)
        icon_size = QSize(14, 14)
        for icon_fn, signal, hover_color in [
            (icon_minimize, self.minimize_clicked, HOVER),
            (icon_maximize, self.maximize_clicked, HOVER),
            (icon_close, self.close_clicked, "#E81123"),
        ]:
            btn = QPushButton()
            btn.setIcon(icon_fn(TEXT_SECONDARY, 14))
            btn.setIconSize(icon_size)
            btn.setFixedSize(36, 28)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            text_hover = "#FFFFFF" if hover_color == "#E81123" else TEXT_PRIMARY
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; border-radius: 4px; }"
                f" QPushButton:hover {{ background-color: {hover_color}; }}"
            )
            btn.clicked.connect(signal.emit)
            layout.addWidget(btn)

    def set_model_name(self, name: str) -> None:
        """Update the displayed model name."""
        self._model_label.setText(name)

    def set_project_path(self, path: str) -> None:
        """Update the displayed project path."""
        self._path_label.setText(path)

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
