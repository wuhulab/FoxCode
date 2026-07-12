# FoxCode Theme Constants and Stylesheet

# Color palette
BG_PRIMARY = "#FFFFFF"
BG_SECONDARY = "#F7F7F8"
BORDER = "#E5E5E5"
TEXT_PRIMARY = "#1A1A1A"
TEXT_SECONDARY = "#6B6B6B"
ACCENT = "#10A37F"
ACCENT_HOVER = "#0D8C6D"
USER_MSG_BG = "#F0F7FF"
HOVER = "#ECECEC"

AVATAR_COLORS = [
    "#6366F1",  # indigo
    "#8B5CF6",  # violet
    "#EC4899",  # pink
    "#F59E0B",  # amber
    "#10B981",  # emerald
    "#3B82F6",  # blue
    "#EF4444",  # red
    "#14B8A6",  # teal
    "#F97316",  # orange
    "#A855F7",  # purple
]


def get_avatar_color(index: int) -> str:
    return AVATAR_COLORS[index % len(AVATAR_COLORS)]


GLOBAL_STYLESHEET = f"""
    * {{
        font-family: 'Segoe UI', 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif;
        outline: none;
    }}
    QMainWindow {{
        background-color: {BG_PRIMARY};
    }}
    QWidget {{
        background-color: {BG_PRIMARY};
        color: {TEXT_PRIMARY};
    }}
    QScrollBar:vertical {{
        background: {BG_PRIMARY};
        width: 6px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        min-height: 30px;
        border-radius: 3px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {TEXT_SECONDARY};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        height: 0;
    }}
    QToolTip {{
        background-color: {TEXT_PRIMARY};
        color: {BG_PRIMARY};
        border: none;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
    }}
"""
