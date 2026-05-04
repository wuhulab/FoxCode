"""
design_mode.py — 设计规范遵守模式状态管理器。

管理 /design on/off 的全局状态，提供设计规范上下文注入功能。
当 design mode 开启时，AI 在前端代码生成时会主动遵守设计规范。

调用方式：
    from foxcode.design_md.design_mode import design_mode_manager
    design_mode_manager.enable()
    design_mode_manager.is_enabled()
    design_mode_manager.get_prompt_injection()
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DesignModeManager:
    """
    设计规范遵守模式管理器。

    管理 /design on/off 的状态切换，提供设计规范上下文注入。
    当启用时，AI 在前端代码生成前会主动调用 design_check 工具
    查看设计令牌并严格遵守。
    """

    def __init__(self) -> None:
        self._enabled = False
        self._design_file_path: Optional[Path] = None
        self._cached_tokens: Optional[str] = None

    def is_enabled(self) -> bool:
        """检查设计规范遵守模式是否已启用。"""
        return self._enabled

    def enable(self) -> str:
        """
        启用设计规范遵守模式。

        查找 .foxcode 目录下的 DESIGN.md 文件，
        启用后 AI 在前端代码生成时会主动遵守设计规范。
        """
        design_file = self._find_design_file()

        if not design_file:
            return (
                "未找到设计规范文件。请在项目根目录或 .foxcode/ 目录下放置 DESIGN.md 文件。\n"
                "设计规范文件搜索路径：\n"
                "  - .foxcode/DESIGN.md\n"
                "  - DESIGN.md\n"
                "  - design.md\n"
                "  - .foxcode/design.md"
            )

        self._enabled = True
        self._design_file_path = design_file
        self._cached_tokens = None  # 清除缓存，下次获取时重新解析

        # 预加载令牌
        tokens = self._load_tokens()
        token_count = 0
        if tokens:
            try:
                data = json.loads(tokens)
                token_count = sum(len(v) if isinstance(v, dict) else 1 for v in data.values())
            except (json.JSONDecodeError, AttributeError):
                pass

        return (
            f"设计规范遵守模式已启用。\n"
            f"规范文件: {design_file}\n"
            f"已加载 {token_count} 个设计令牌。\n"
            f"AI 在前端代码生成时会主动调用 design_check 工具查看并遵守规范。"
        )

    def disable(self) -> str:
        """禁用设计规范遵守模式。"""
        self._enabled = False
        self._design_file_path = None
        self._cached_tokens = None
        return "设计规范遵守模式已禁用。AI 将不再主动检查设计规范。"

    def get_prompt_injection(self) -> str:
        """
        获取要注入到系统提示词中的设计规范上下文。

        仅在 design mode 启用且有设计文件时返回内容。
        """
        if not self._enabled:
            return ""

        tokens = self._load_tokens()
        if not tokens:
            return ""

        return (
            "\n\n================================================================================\n"
            "## DESIGN COMPLIANCE MODE (ACTIVE)\n"
            "================================================================================\n"
            "Design compliance mode is ENABLED. You MUST follow the project's design tokens\n"
            "when generating frontend code (HTML, CSS, Vue, React, etc.).\n\n"
            "**RULES:**\n"
            "1. Use design_check tool to get tokens BEFORE writing frontend code\n"
            "2. NEVER hardcode colors - always use design token values\n"
            "3. NEVER hardcode spacing/border-radius - always use design token values\n"
            "4. NEVER hardcode font properties - always use design token values\n"
            "5. If a value is not in the design tokens, use the closest available token\n\n"
            "**Available Design Tokens:**\n"
            f"```json\n{tokens}\n```\n\n"
            "Use <function=design_check><parameter=action>tokens</parameter></function> to refresh tokens.\n"
            "Use <function=design_check><parameter=action>check</parameter><parameter=code_snippet>YOUR_CODE</parameter></function> to verify compliance.\n"
            "================================================================================\n"
        )

    def get_design_file_path(self) -> Optional[Path]:
        """获取当前使用的设计规范文件路径。"""
        return self._design_file_path

    def _find_design_file(self) -> Optional[Path]:
        """在项目目录下查找 DESIGN.md 文件。"""
        search_paths = [
            Path.cwd() / ".foxcode" / "DESIGN.md",
            Path.cwd() / "DESIGN.md",
            Path.cwd() / "design.md",
            Path.cwd() / ".foxcode" / "design.md",
        ]

        for path in search_paths:
            if path.exists() and path.is_file():
                return path

        return None

    def _load_tokens(self) -> str:
        """加载并缓存设计令牌。"""
        if self._cached_tokens is not None:
            return self._cached_tokens

        if not self._design_file_path or not self._design_file_path.exists():
            return ""

        try:
            content = self._design_file_path.read_text(encoding="utf-8")
            from foxcode.design_md.lint import lint

            report = lint(content)
            ds = report.designSystem

            tokens = {}

            # 颜色令牌
            if ds.colors:
                tokens["colors"] = {name: color.hex for name, color in ds.colors.items()}

            # 排版令牌
            if ds.typography:
                typography = {}
                for name, typo in ds.typography.items():
                    props = {}
                    if typo.fontFamily:
                        props["fontFamily"] = typo.fontFamily
                    if typo.fontSize:
                        props["fontSize"] = f"{typo.fontSize.value}{typo.fontSize.unit}"
                    if typo.fontWeight is not None:
                        props["fontWeight"] = typo.fontWeight
                    if typo.lineHeight:
                        props["lineHeight"] = f"{typo.lineHeight.value}{typo.lineHeight.unit}"
                    typography[name] = props
                tokens["typography"] = typography

            # 圆角令牌
            if ds.rounded:
                tokens["borderRadius"] = {name: f"{dim.value}{dim.unit}" for name, dim in ds.rounded.items()}

            # 间距令牌
            if ds.spacing:
                tokens["spacing"] = {name: f"{dim.value}{dim.unit}" for name, dim in ds.spacing.items()}

            # 组件令牌
            if ds.components:
                components = {}
                for name, comp in ds.components.items():
                    comp_props = {}
                    for prop_name, prop_val in comp.properties.items():
                        if hasattr(prop_val, "hex"):
                            comp_props[prop_name] = prop_val.hex
                        elif hasattr(prop_val, "value"):
                            comp_props[prop_name] = f"{prop_val.value}{prop_val.unit}"
                        else:
                            comp_props[prop_name] = str(prop_val)
                    components[name] = comp_props
                tokens["components"] = components

            self._cached_tokens = json.dumps(tokens, indent=2, ensure_ascii=False)
            return self._cached_tokens

        except Exception as e:
            logger.error("加载设计令牌失败: %s", e)
            return ""


# 全局单例
design_mode_manager = DesignModeManager()
