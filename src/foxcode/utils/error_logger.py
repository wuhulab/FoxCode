"""Error logger - captures all exceptions and writes to two local files.

  fc_error.log     – program bugs (exceptions originating from foxcode's own code)
  fc_ot_error.log  – other issues (external/operational errors: network, IO, API, etc.)

Usage:
    from foxcode.utils.error_logger import install_hooks, log_exception

    # Install global hooks (sys.excepthook, threading.excepthook)
    install_hooks()

    # Manual logging from a try/except block
    try:
        ...
    except Exception:
        log_exception(context="chat_worker")
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

ERROR_LOG_DIR = Path.home() / ".foxcode"
FC_ERROR_LOG = ERROR_LOG_DIR / "fc_error.log"
FC_OT_ERROR_LOG = ERROR_LOG_DIR / "fc_ot_error.log"

_lock = threading.Lock()
_logger = logging.getLogger("foxcode.error_logger")

# Exception types that are clearly operational (external/environmental) errors.
# These go to fc_ot_error.log regardless of traceback origin.
_OPERATIONAL_TYPES = (
    OSError,
    IOError,
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
    ConnectionAbortedError,
    TimeoutError,
    FileNotFoundError,
    PermissionError,
    IsADirectoryError,
    NotADirectoryError,
    FileExistsError,
    InterruptedError,
    BlockingIOError,
    ChildProcessError,
    BrokenPipeError,
    BufferError,
    EOFError,
)


def _get_exception_source(exc_traceback) -> Optional[str]:
    """Determine if the exception originated from foxcode code or external code.

    Returns 'internal', 'external', or None.
    """
    tb = exc_traceback
    if tb is None:
        return None

    # Walk the traceback to find the innermost frame (origin of the exception)
    frames = []
    current = tb
    while current is not None:
        frames.append(current.tb_frame)
        current = current.tb_next

    if not frames:
        return None

    innermost_frame = frames[-1]
    filename = innermost_frame.f_code.co_filename
    filename = os.path.normpath(filename).replace("\\", "/")

    if "foxcode" in filename:
        return "internal"

    return "external"


def _classify(
    exc_type: type,
    exc_value: BaseException,
    exc_traceback: Optional[type],
) -> Optional[str]:
    """Classify an exception as 'bug' (program bug) or 'operational' (other).

    Returns None for exceptions that should not be logged (KeyboardInterrupt, etc.).
    """
    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        return None

    for op_type in _OPERATIONAL_TYPES:
        if issubclass(exc_type, op_type):
            return "operational"

    source = _get_exception_source(exc_traceback)
    if source == "internal":
        return "bug"

    return "operational"


def log_exception(
    exc_type: Optional[type] = None,
    exc_value: Optional[BaseException] = None,
    exc_traceback: Optional[type] = None,
    context: Optional[str] = None,
) -> None:
    """Log an exception to the appropriate file.

    If called without arguments, uses sys.exc_info() to get the current exception.

    Args:
        exc_type: Exception type (or None to use sys.exc_info()).
        exc_value: Exception instance (or None).
        exc_traceback: Traceback object (or None).
        context: Optional string describing where the error occurred.
    """
    if exc_type is None:
        exc_type, exc_value, exc_traceback = sys.exc_info()
    if exc_type is None:
        return

    category = _classify(exc_type, exc_value, exc_traceback)
    if category is None:
        return

    log_path = ERROR_LOG_DIR / f"fc_{'error' if category == 'bug' else 'ot_error'}.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    tb_text = "".join(
        traceback.format_exception(exc_type, exc_value, exc_traceback)
    )

    tag = f"[{context}] " if context else ""
    entry = (
        f"[{timestamp}] {tag}{exc_type.__name__}: {exc_value}\n"
        f"{tb_text}"
        f"{'-' * 60}\n"
    )

    with _lock:
        ERROR_LOG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            _logger.error(f"写入错误日志失败 [{log_path}]: {e}")


def _global_exception_hook(
    exc_type: type,
    exc_value: BaseException,
    exc_traceback: Optional[type],
) -> None:
    """sys.excepthook replacement - logs all unhandled exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        return
    log_exception(exc_type, exc_value, exc_traceback, context="unhandled")
    _logger.critical(
        "未捕获的全局异常:",
        exc_info=(exc_type, exc_value, exc_traceback),
    )


def _thread_exception_hook(args: threading.ExceptHookArgs) -> None:
    """threading.excepthook replacement."""
    log_exception(
        args.exc_type,
        args.exc_value,
        args.exc_traceback,
        context=f"thread:{args.thread.name}",
    )
    _logger.critical(
        f"线程 [{args.thread.name}] 未捕获异常:",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def install_hooks() -> None:
    """Install global exception hooks for error logging.

    Replaces sys.excepthook and threading.excepthook so that all
    unhandled exceptions are captured to the appropriate log file.
    """
    ERROR_LOG_DIR.mkdir(parents=True, exist_ok=True)
    sys.excepthook = _global_exception_hook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_exception_hook
    _logger.info("错误日志钩子已安装 → %s", ERROR_LOG_DIR)
