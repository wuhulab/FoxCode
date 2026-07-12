"""FoxCode PySide Desktop GUI - 应用入口"""
import sys
import logging
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from foxcode.pyside_gui.main_window import MainWindow

logger = logging.getLogger(__name__)


def start_pyside_gui(
    agent=None,
    config=None,
) -> int:
    """启动 PySide 桌面 GUI。

    Parameters
    ----------
    agent : FoxCodeAgent | None
        已初始化的 agent 实例。为 None 时 GUI 仍可启动但无法与 AI 交互。
    config : Config | None
        FoxCode 配置（留作扩展用）。

    Returns
    -------
    int
        应用退出码。
    """
    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("FoxCode")
    app.setApplicationVersion("0.1.5")
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow(agent=agent)
    window.show()

    logger.info("PySide GUI started")
    return app.exec()


if __name__ == "__main__":
    sys.exit(start_pyside_gui())
