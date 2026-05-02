"""
FoxCode 配置验证模块 - 确保配置的正确性和安全性

这个文件提供配置验证功能:
1. 格式验证：检查配置项的格式是否正确
2. 安全验证：检查配置是否存在安全风险（如不安全的权限）
3. 依赖验证：检查配置的依赖是否满足
4. 错误报告：生成详细的验证错误报告

验证内容:
- API Key 格式和有效性
- 文件路径和权限
- 端口号范围
- 模型名称是否支持
- 沙箱配置安全性

使用方式:
    from foxcode.core.config_validator import ConfigValidator

    validator = ConfigValidator()
    is_valid, errors, warnings = validator.validate(config)
"""

from __future__ import annotations

import logging
import os
import platform
import re
import stat
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """配置验证错误"""

    def __init__(self, errors: list[dict[str, Any]]):
        """
        初始化配置验证错误
        
        Args:
            errors: 错误列表
        """
        self.errors = errors
        super().__init__(self._format_errors(errors))

    def _format_errors(self, errors: list[dict[str, Any]]) -> str:
        """格式化错误信息"""
        lines = ["配置验证失败:"]
        for error in errors:
            field = error.get("field", "未知字段")
            message = error.get("message", "未知错误")
            lines.append(f"  - {field}: {message}")
        return "\n".join(lines)


class ConfigValidator:
    """
    配置验证器
    
    验证配置文件的正确性和完整性
    """

    # 必需的配置字段
    REQUIRED_FIELDS = {
        "model": ["provider"],
    }

    # 字段类型验证
    FIELD_TYPES = {
        "model.provider": str,
        "model.model_name": str,
        "model.api_key": (str, type(None)),
        "model.base_url": (str, type(None)),
        "model.temperature": (int, float),
        "model.max_tokens": int,
        "model.timeout": int,
        "tools.enable_file_ops": bool,
        "tools.enable_shell": bool,
        "tools.enable_web_search": bool,
        "tools.shell_timeout": int,
        "tools.max_file_size": int,
        "ui.theme": str,
        "ui.show_token_usage": bool,
        "ui.show_timing": bool,
        "session.auto_save_session": bool,
        "session.max_history": int,
    }

    # 字段值范围
    FIELD_RANGES = {
        "model.temperature": (0.0, 2.0),
        "model.max_tokens": (1, 1000000),
        "model.timeout": (1, 3600),
        "tools.shell_timeout": (1, 3600),
        "tools.max_file_size": (1, 1024 * 1024 * 1024),  # 最大 1GB
        "session.max_history": (0, 10000),
    }

    # 枚举值验证
    FIELD_ENUMS = {
        "model.provider": ["openai", "anthropic", "deepseek", "step", "local", "custom"],
        "ui.theme": ["dark", "light", "auto"],
    }

    # API Key 格式验证
    API_KEY_PATTERNS = {
        "openai": r"^sk-[a-zA-Z0-9]{20,}$",
        "anthropic": r"^sk-ant-[a-zA-Z0-9-]{20,}$",
        "deepseek": r"^sk-[a-zA-Z0-9]{20,}$",
        "step": r"^sk-[a-zA-Z0-9]{20,}$",
    }

    def __init__(self):
        """初始化配置验证器"""
        self.errors: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []

    def validate(self, config: dict[str, Any]) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
        """
        验证配置
        
        Args:
            config: 配置字典
            
        Returns:
            (是否有效, 错误列表, 警告列表)
        """
        self.errors = []
        self.warnings = []

        # 0. 验证配置文件权限（安全检查）
        if "_config_path" in config:
            self._validate_config_file_permissions(config["_config_path"])

        # 1. 验证必需字段
        self._validate_required_fields(config)

        # 2. 验证字段类型
        self._validate_field_types(config)

        # 3. 验证字段值范围
        self._validate_field_ranges(config)

        # 4. 验证枚举值
        self._validate_enums(config)

        # 5. 验证 API Key 格式
        self._validate_api_keys(config)

        # 6. 验证路径
        self._validate_paths(config)

        # 7. 验证逻辑一致性
        self._validate_consistency(config)

        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_config_file_permissions(self, config_path: str | Path) -> None:
        """
        验证配置文件权限（安全检查）
        
        检查配置文件是否包含敏感信息且权限设置不当。
        
        Args:
            config_path: 配置文件路径
        """
        path = Path(config_path)

        if not path.exists():
            return

        try:
            # 检查文件权限
            file_stat = path.stat()
            mode = file_stat.st_mode

            system = platform.system()

            if system != "Windows":
                # Unix/Linux/Mac: 检查文件权限位
                # 检查是否其他用户可读
                if mode & stat.S_IROTH:
                    self.warnings.append({
                        "field": "_config_path",
                        "message": f"配置文件 '{config_path}' 对其他用户可读，可能泄露敏感信息。建议运行: chmod 600 {config_path}",
                    })

                # 检查是否其他用户可写
                if mode & stat.S_IWOTH:
                    self.errors.append({
                        "field": "_config_path",
                        "message": f"配置文件 '{config_path}' 对其他用户可写，存在严重安全风险。请立即运行: chmod 600 {config_path}",
                    })

                # 检查是否组用户可写
                if mode & stat.S_IWGRP:
                    self.warnings.append({
                        "field": "_config_path",
                        "message": f"配置文件 '{config_path}' 对组用户可写，存在安全风险。建议运行: chmod 600 {config_path}",
                    })
            else:
                # Windows: 检查文件是否在用户目录外
                user_profile = os.environ.get("USERPROFILE", "")
                try:
                    if user_profile and not str(path.resolve()).startswith(user_profile):
                        self.warnings.append({
                            "field": "_config_path",
                            "message": f"配置文件 '{config_path}' 不在用户目录中，可能被其他用户访问",
                        })
                except Exception:
                    pass

            # 检查文件是否包含敏感信息
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                sensitive_patterns = [
                    (r'api_key\s*=\s*["\']?sk-[a-zA-Z0-9]{10,}', "API Key"),
                    (r'password\s*=\s*["\']?[^\s"\']{4,}', "密码"),
                    (r'secret\s*=\s*["\']?[a-zA-Z0-9]{8,}', "密钥"),
                    (r'token\s*=\s*["\']?[a-zA-Z0-9]{10,}', "令牌"),
                ]

                for pattern, sensitive_type in sensitive_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        # 如果包含敏感信息，加强权限检查
                        if system != "Windows" and (mode & stat.S_IROTH or mode & stat.S_IRGRP):
                            self.warnings.append({
                                "field": "_config_path",
                                "message": f"配置文件包含 {sensitive_type} 且对其他用户/组可读，强烈建议设置权限为 600",
                            })
                        break
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"检查配置文件权限失败: {e}")

    def _validate_required_fields(self, config: dict[str, Any]) -> None:
        """验证必需字段"""
        for section, fields in self.REQUIRED_FIELDS.items():
            section_config = config.get(section, {})
            if not isinstance(section_config, dict):
                self.errors.append({
                    "field": section,
                    "message": f"配置节 '{section}' 必须是一个字典",
                })
                continue

            for field in fields:
                if field not in section_config or section_config[field] is None:
                    self.errors.append({
                        "field": f"{section}.{field}",
                        "message": "缺少必需字段",
                    })

    def _validate_field_types(self, config: dict[str, Any]) -> None:
        """验证字段类型"""
        for field_path, expected_type in self.FIELD_TYPES.items():
            value = self._get_nested_value(config, field_path)
            if value is None:
                continue  # 可选字段，跳过

            if not isinstance(value, expected_type):
                # 处理元组类型（多个可能的类型）
                if isinstance(expected_type, tuple):
                    type_names = " 或 ".join(t.__name__ for t in expected_type)
                else:
                    type_names = expected_type.__name__

                self.errors.append({
                    "field": field_path,
                    "message": f"类型错误，期望 {type_names}，实际 {type(value).__name__}",
                })

    def _validate_field_ranges(self, config: dict[str, Any]) -> None:
        """验证字段值范围"""
        for field_path, (min_val, max_val) in self.FIELD_RANGES.items():
            value = self._get_nested_value(config, field_path)
            if value is None:
                continue

            if isinstance(value, (int, float)):
                if value < min_val or value > max_val:
                    self.errors.append({
                        "field": field_path,
                        "message": f"值 {value} 超出范围 [{min_val}, {max_val}]",
                    })

    def _validate_enums(self, config: dict[str, Any]) -> None:
        """验证枚举值"""
        for field_path, valid_values in self.FIELD_ENUMS.items():
            value = self._get_nested_value(config, field_path)
            if value is None:
                continue

            if value not in valid_values:
                self.errors.append({
                    "field": field_path,
                    "message": f"无效值 '{value}'，有效值为: {', '.join(valid_values)}",
                })

    def _validate_api_keys(self, config: dict[str, Any]) -> None:
        """验证 API Key 格式"""
        model_config = config.get("model", {})
        provider = model_config.get("provider", "")
        api_key = model_config.get("api_key")

        if not api_key:
            # 检查环境变量
            self.warnings.append({
                "field": "model.api_key",
                "message": "未配置 API Key，将尝试从环境变量获取",
            })
            return

        # 验证 API Key 格式
        if provider in self.API_KEY_PATTERNS:
            pattern = self.API_KEY_PATTERNS[provider]
            if not re.match(pattern, api_key):
                self.warnings.append({
                    "field": "model.api_key",
                    "message": f"API Key 格式可能不正确（期望匹配模式: {pattern[:20]}...）",
                })

    def _validate_paths(self, config: dict[str, Any]) -> None:
        """验证路径"""
        # 验证工作目录
        working_dir = config.get("working_dir")
        if working_dir:
            path = Path(working_dir)
            if not path.exists():
                self.errors.append({
                    "field": "working_dir",
                    "message": f"工作目录不存在: {working_dir}",
                })
            elif not path.is_dir():
                self.errors.append({
                    "field": "working_dir",
                    "message": f"工作目录路径不是目录: {working_dir}",
                })

        # 验证会话目录
        session_dir = config.get("session_dir")
        if session_dir:
            path = Path(session_dir)
            if path.exists() and not path.is_dir():
                self.errors.append({
                    "field": "session_dir",
                    "message": f"会话目录路径不是目录: {session_dir}",
                })

        # 验证 base_url
        base_url = config.get("model", {}).get("base_url")
        if base_url:
            if not base_url.startswith(("http://", "https://")):
                self.errors.append({
                    "field": "model.base_url",
                    "message": "base_url 必须以 http:// 或 https:// 开头",
                })

    def _validate_consistency(self, config: dict[str, Any]) -> None:
        """验证逻辑一致性"""
        model_config = config.get("model", {})
        tools_config = config.get("tools", {})
        sandbox_config = config.get("sandbox", {})
        run_mode = config.get("run_mode", "default")

        if model_config.get("provider") == "local":
            base_url = model_config.get("base_url")
            if not base_url:
                self.warnings.append({
                    "field": "model.base_url",
                    "message": "本地模型需要指定模型路径（base_url）",
                })

        if tools_config.get("enable_shell"):
            shell_timeout = tools_config.get("shell_timeout", 300)
            if shell_timeout > 600:
                self.warnings.append({
                    "field": "tools.shell_timeout",
                    "message": f"Shell 超时时间设置较长（{shell_timeout}秒），可能影响响应速度",
                })

        allowed_extensions = tools_config.get("allowed_extensions", [])
        if allowed_extensions:
            for ext in allowed_extensions:
                if not ext.startswith("."):
                    self.warnings.append({
                        "field": "tools.allowed_extensions",
                        "message": f"文件扩展名 '{ext}' 应以点号开头（如 '.py'）",
                    })

        self._validate_dangerous_config_combinations(config, tools_config, sandbox_config, run_mode)

    def _validate_dangerous_config_combinations(
        self,
        config: dict[str, Any],
        tools_config: dict[str, Any],
        sandbox_config: dict[str, Any],
        run_mode: str,
    ) -> None:
        """
        验证危险配置组合
        
        检测可能导致安全风险的配置组合
        """
        enable_shell = tools_config.get("enable_shell", True)
        enable_file_ops = tools_config.get("enable_file_ops", True)
        sandbox_enabled = sandbox_config.get("enabled", True)
        sandbox_mode = sandbox_config.get("mode", "blacklist")
        allow_path_traversal = sandbox_config.get("allow_path_traversal", False)

        if run_mode == "yolo":
            if enable_shell and not sandbox_enabled:
                raise ValueError(
                    "危险配置组合: YOLO 模式下启用了 Shell 执行但禁用了沙箱，存在严重安全风险。 "
                    "请使用 --force 参数强制使用此配置，或使用 --no-shell 参数完全禁用此功能"
                )

            if enable_shell and sandbox_enabled and allow_path_traversal:
                raise ValueError(
                    "危险配置组合: YOLO 模式下允许路径穿越，存在严重安全风险。 "
                    "请使用 --force 参数强制使用此配置，或使用 --no-shell 参数完全禁用此功能"
                )

            if enable_shell and sandbox_mode == "disabled":
                raise ValueError(
                    "危险配置组合: YOLO 模式下沙箱模式为禁用状态，存在严重安全风险。 "
                    "请使用 --force 参数强制使用此配置，或使用 --no-shell 参数完全禁用此功能"
                )

            if enable_shell and not sandbox_enabled:
                self.warnings.append({
                    "field": "sandbox.enabled",
                    "message": "启用了 Shell 执行但禁用了沙箱，建议启用沙箱以增强安全性",
                })

        if enable_shell and allow_path_traversal:
            self.warnings.append({
                "field": "sandbox.allow_path_traversal",
                "message": "启用了 Shell 执行并允许路径穿越，可能导致目录穿越攻击",
            })

        if enable_file_ops and allow_path_traversal:
            self.warnings.append({
                "field": "sandbox.allow_path_traversal",
                "message": "启用了文件操作并允许路径穿越，可能导致敏感文件泄露",
            })

        if sandbox_mode == "whitelist":
            allowed_commands = sandbox_config.get("allowed_commands", [])
            if not allowed_commands:
                self.warnings.append({
                    "field": "sandbox.allowed_commands",
                    "message": "白名单模式下未配置允许的命令列表，将拒绝所有命令",
                })

        security_config = config.get("security", {})
        if security_config:
            session_timeout = security_config.get("session_timeout", 3600)
            if session_timeout < 300:
                self.warnings.append({
                    "field": "security.session_timeout",
                    "message": f"会话超时时间过短（{session_timeout}秒），可能导致频繁重新认证",
                })

            if session_timeout > 86400:
                self.warnings.append({
                    "field": "security.session_timeout",
                    "message": f"会话超时时间过长（{session_timeout}秒），存在安全风险",
                })

        content_filter = config.get("content_filter", {})
        if content_filter:
            security_level = content_filter.get("security_level", "medium")
            if security_level == "low" and enable_shell:
                self.warnings.append({
                    "field": "content_filter.security_level",
                    "message": "安全级别为低且启用了 Shell 执行，建议提高安全级别",
                })

    def _get_nested_value(self, config: dict[str, Any], path: str) -> Any:
        """
        获取嵌套值
        
        Args:
            config: 配置字典
            path: 字段路径（如 "model.provider"）
            
        Returns:
            字段值
        """
        keys = path.split(".")
        value = config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def get_validation_report(self) -> str:
        """
        获取验证报告
        
        Returns:
            格式化的验证报告
        """
        lines = ["📋 配置验证报告", "=" * 40]

        if self.errors:
            lines.append("\n❌ 错误:")
            for error in self.errors:
                lines.append(f"  • {error['field']}: {error['message']}")
        else:
            lines.append("\n✅ 没有发现错误")

        if self.warnings:
            lines.append("\n⚠️ 警告:")
            for warning in self.warnings:
                lines.append(f"  • {warning['field']}: {warning['message']}")

        return "\n".join(lines)


def validate_config(config: dict[str, Any]) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
    """
    验证配置
    
    Args:
        config: 配置字典
        
    Returns:
        (是否有效, 错误列表, 警告列表)
    """
    validator = ConfigValidator()
    return validator.validate(config)


def validate_config_file(config_path: Path) -> tuple[bool, str]:
    """
    验证配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        (是否有效, 验证报告)
    """
    import sys
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
    except Exception as e:
        return False, f"无法读取配置文件: {e}"

    validator = ConfigValidator()
    is_valid, errors, warnings = validator.validate(config)

    return is_valid, validator.get_validation_report()
