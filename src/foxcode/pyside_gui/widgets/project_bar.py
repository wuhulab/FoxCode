from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QPainter, QColor, QBrush, QPen, QMouseEvent

from foxcode.pyside_gui.theme import (
    BG_SECONDARY, BORDER, ACCENT, HOVER, TEXT_PRIMARY, get_avatar_color,
)


class ProjectAvatar(QWidget):
    """A small colored square with the first letter of a project name."""

    clicked = Signal(int)

    def __init__(self, name: str, index: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.name = name
        self.index = index
        self.letter = name[0].upper() if name else "?"
        self.color = QColor(get_avatar_color(index))
        self._active = False
        self._hovered = False
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(name)

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool):
        self._active = value
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw rounded rect background
        rect = self.rect().adjusted(0, 0, -1, -1)
        if self._active:
            painter.setBrush(QBrush(self.color))
            painter.setPen(QPen(QColor(ACCENT), 2))
        elif self._hovered:
            lighter = QColor(self.color)
            lighter.setAlpha(220)
            painter.setBrush(QBrush(lighter))
            painter.setPen(Qt.PenStyle.NoPen)
        else:
            painter.setBrush(QBrush(self.color))
            painter.setPen(Qt.PenStyle.NoPen)

        painter.drawRoundedRect(rect, 8, 8)

        # Draw letter
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.letter)
        painter.end()


class ProjectBar(QWidget):
    """Leftmost narrow bar showing project avatars."""

    project_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(48)
        self.setStyleSheet(f"""
            ProjectBar {{
                background-color: {BG_SECONDARY};
                border-right: 1px solid {BORDER};
            }}
        """)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(6, 12, 6, 12)
        self._layout.setSpacing(8)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self._avatars: list[ProjectAvatar] = []
        self._active_index = -1

        # Demo projects
        demo_projects = ["FoxCode", "Backend", "Dashboard", "Mobile", "Infra"]
        for i, name in enumerate(demo_projects):
            self.add_project(name, i)

        if self._avatars:
            self._set_active(0)

        self._layout.addStretch()

    def add_project(self, name: str, index: int):
        avatar = ProjectAvatar(name, index)
        avatar.clicked.connect(self._on_avatar_clicked)
        self._avatars.append(avatar)
        self._layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignHCenter)

    def _on_avatar_clicked(self, index: int):
        self._set_active(index)
        self.project_selected.emit(index)

    def _set_active(self, index: int):
        self._active_index = index
        for avatar in self._avatars:
            avatar.active = avatar.index == index
