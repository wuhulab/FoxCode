"""FoxCode PySide GUI - SVG 图标系统（替代所有 unicode/emoji）"""
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray, QSize, Qt


def _svg_to_icon(svg: str, size: int = 24) -> QIcon:
    """将 SVG 字符串转为 QIcon。"""
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def _svg_to_pixmap(svg: str, size: int = 24) -> QPixmap:
    """将 SVG 字符串转为 QPixmap。"""
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


# ── SVG 源码 ──────────────────────────────────────────

_SEND = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <line x1="22" y1="2" x2="11" y2="13"/>
  <polygon points="22 2 15 22 11 13 2 9 22 2"/>
</svg>"""

_SETTINGS = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="3"/>
  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06
    a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09
    A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83
    l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09
    A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83
    l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09
    a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83
    l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09
    a1.65 1.65 0 0 0-1.51 1z"/>
</svg>"""

_MINIMIZE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round">
  <line x1="5" y1="12" x2="19" y2="12"/>
</svg>"""

_MAXIMIZE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
</svg>"""

_CLOSE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round">
  <line x1="18" y1="6" x2="6" y2="18"/>
  <line x1="6" y1="6" x2="18" y2="18"/>
</svg>"""

_NEW_CHAT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <line x1="12" y1="5" x2="12" y2="19"/>
  <line x1="5" y1="12" x2="19" y2="12"/>
</svg>"""

_MODEL_DOT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">
  <circle cx="6" cy="6" r="5" fill="{color}"/>
</svg>"""

_CHAT_BUBBLE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
</svg>"""

_FOLDER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
</svg>"""

_LOADING = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round">
  <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
</svg>"""

_WARNING = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86
    a2 2 0 0 0-3.42 0z"/>
  <line x1="12" y1="9" x2="12" y2="13"/>
  <line x1="12" y1="17" x2="12.01" y2="17"/>
</svg>"""

_COPY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
</svg>"""


# ── 公开 API ──────────────────────────────────────────

def icon_send(size: int = 20) -> QIcon:
    return _svg_to_icon(_SEND, size)

def icon_settings(color: str = "#6B6B6B", size: int = 20) -> QIcon:
    return _svg_to_icon(_SETTINGS.format(color=color), size)

def icon_minimize(color: str = "#6B6B6B", size: int = 16) -> QIcon:
    return _svg_to_icon(_MINIMIZE.format(color=color), size)

def icon_maximize(color: str = "#6B6B6B", size: int = 16) -> QIcon:
    return _svg_to_icon(_MAXIMIZE.format(color=color), size)

def icon_close(color: str = "#6B6B6B", size: int = 16) -> QIcon:
    return _svg_to_icon(_CLOSE.format(color=color), size)

def icon_new_chat(color: str = "#FFFFFF", size: int = 16) -> QIcon:
    return _svg_to_icon(_NEW_CHAT.format(color=color), size)

def icon_model_dot(color: str = "#10A37F", size: int = 10) -> QPixmap:
    return _svg_to_pixmap(_MODEL_DOT.format(color=color), size)

def icon_chat_bubble(color: str = "#6B6B6B", size: int = 16) -> QIcon:
    return _svg_to_icon(_CHAT_BUBBLE.format(color=color), size)

def icon_folder(color: str = "#6B6B6B", size: int = 20) -> QIcon:
    return _svg_to_icon(_FOLDER.format(color=color), size)

def icon_loading(color: str = "#10A37F", size: int = 20) -> QPixmap:
    return _svg_to_pixmap(_LOADING.format(color=color), size)

def icon_warning(color: str = "#F59E0B", size: int = 16) -> QPixmap:
    return _svg_to_pixmap(_WARNING.format(color=color), size)

def icon_copy(color: str = "#6B6B6B", size: int = 16) -> QIcon:
    return _svg_to_icon(_COPY.format(color=color), size)
