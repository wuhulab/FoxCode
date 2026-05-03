"""
utils.py — 工具函数。

提供 read_input、format_output、serialize_design_system、diff_maps 等通用函数。

调用方式：
    from foxcode.design_md.utils import read_input, diff_maps
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional


def read_input(file_path: str) -> str:
    """从文件路径或 stdin 读取内容。file_path 为 "-" 时从 stdin 读取。"""
    if file_path == "-":
        return sys.stdin.read()

    try:
        return Path(file_path).read_text(encoding="utf-8")
    except Exception as e:
        print(json.dumps({
            "error": "FILE_READ_ERROR",
            "message": str(e),
            "path": file_path,
        }), file=sys.stderr)
        raise


def format_output(data: Any, fmt: str = "json") -> str:
    """将数据格式化为 JSON 或 Markdown 文本。"""
    if fmt in ("markdown", "md"):
        return _format_as_markdown(data)

    return json.dumps(data, default=_json_default, indent=2, ensure_ascii=False)


def serialize_design_system(state: dict[str, Any]) -> dict[str, Any]:
    """将 dict-based DesignSystemState 序列化为可 JSON 化的 plain dict。"""
    result = {}
    for key, value in state.items():
        if isinstance(value, dict):
            result[key] = _serialize_dict(value)
        else:
            result[key] = value
    return result


def diff_maps(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, list[str]]:
    """比较两个 dict，返回 added/removed/modified 键列表。"""
    added = []
    removed = []
    modified = []

    for key in after:
        if key not in before:
            added.append(key)
        elif json.dumps(before[key], default=_json_default) != json.dumps(after[key], default=_json_default):
            modified.append(key)

    for key in before:
        if key not in after:
            removed.append(key)

    return {"added": added, "removed": removed, "modified": modified}


def _json_default(obj: Any) -> Any:
    """JSON 序列化默认处理器，处理 dataclass 和其他特殊类型。"""
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _serialize_dict(d: dict[str, Any]) -> dict[str, Any]:
    """递归序列化 dict 中的特殊类型。"""
    result = {}
    for key, value in d.items():
        if hasattr(value, "__dict__") and not isinstance(value, dict):
            result[key] = value.__dict__
        elif isinstance(value, dict):
            result[key] = _serialize_dict(value)
        else:
            result[key] = value
    return result


def _format_as_markdown(data: Any) -> str:
    """将数据格式化为 Markdown 文本。"""
    if isinstance(data, dict):
        result = ""
        if "summary" in data:
            result += f"# {data['summary']}\n\n"
        if "details" in data:
            result += "## Details\n\n"
            result += _format_as_text(data["details"])
            result += "\n"
        return result or _format_as_text(data)

    return str(data)


def _format_as_text(data: Any, indent: int = 0) -> str:
    """将数据格式化为缩进文本。"""
    if data is None:
        return "null"

    if isinstance(data, str):
        return data

    if isinstance(data, (int, float, bool)):
        return str(data)

    if isinstance(data, list):
        return "\n".join(
            f"{'  ' * indent}- {_format_as_text(item, indent + 1)}"
            for item in data
        )

    if isinstance(data, dict):
        return "\n".join(
            f"{'  ' * indent}{key}: {_format_as_text(val, indent + 1) if not isinstance(val, dict) else ''}\n{_format_as_text(val, indent + 1) if isinstance(val, dict) else ''}"
            for key, val in data.items()
        )

    return str(data)
