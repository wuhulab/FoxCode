"""
FoxCode 钩子系统基础组件

定义钩子系统的核心组件，包括钩子类型、上下文和管理器
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TypeVar, Generic, List

logger = logging.getLogger(__name__)


T = TypeVar('T')


class HookType(str, Enum):
    """钩子类型"""
    # 应用生命周期钩子
    APP_STARTUP = "app_startup"  # 应用启动时
    APP_SHUTDOWN = "app_shutdown"  # 应用关闭时
    
    # 命令生命周期钩子
    COMMAND_PRE_EXECUTE = "command_pre_execute"  # 命令执行前
    COMMAND_POST_EXECUTE = "command_post_execute"  # 命令执行后
    COMMAND_ERROR = "command_error"  # 命令执行错误时
    
    # 工具生命周期钩子
    TOOL_PRE_EXECUTE = "tool_pre_execute"  # 工具执行前
    TOOL_POST_EXECUTE = "tool_post_execute"  # 工具执行后
    TOOL_ERROR = "tool_error"  # 工具执行错误时
    
    # 会话生命周期钩子
    SESSION_START = "session_start"  # 会话开始时
    SESSION_END = "session_end"  # 会话结束时
    SESSION_SAVE = "session_save"  # 会话保存时
    
    # 技能生命周期钩子
    SKILL_PRE_EXECUTE = "skill_pre_execute"  # 技能执行前
    SKILL_POST_EXECUTE = "skill_post_execute"  # 技能执行后
    SKILL_ERROR = "skill_error"  # 技能执行错误时
    
    # 工作模式钩子
    WORK_MODE_START = "work_mode_start"  # 工作模式开始时
    WORK_MODE_END = "work_mode_end"  # 工作模式结束时
    WORK_MODE_STEP_CHANGE = "work_mode_step_change"  # 工作模式步骤变化时
    
    # 配置钩子
    CONFIG_LOADED = "config_loaded"  # 配置加载后
    CONFIG_UPDATED = "config_updated"  # 配置更新后
    
    # 工具注册钩子
    TOOL_REGISTERED = "tool_registered"  # 工具注册时
    
    # 服务钩子
    SERVICE_START = "service_start"  # 服务启动时
    SERVICE_STOP = "service_stop"  # 服务停止时


@dataclass
class HookContext(Generic[T]):
    """钩子上下文"""
    hook_type: HookType  # 钩子类型
    data: T  # 钩子数据
    config: Any = None  # 配置
    metadata: dict[str, Any] = field(default_factory=dict)  # 元数据


class HookHandler(Generic[T]):
    """钩子处理器"""
    
    def __init__(self, callback: Callable[[HookContext[T]], Any], priority: int = 0):
        """
        初始化钩子处理器
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        self.callback = callback
        self.priority = priority


class HookManager:
    """钩子管理器"""
    
    def __init__(self):
        """初始化钩子管理器"""
        self._hooks: dict[HookType, List[HookHandler[Any]]] = {}
        self._logger = logging.getLogger("foxcode.core.hooks")
    
    def register(self, hook_type: HookType, callback: Callable[[HookContext[Any]], Any], priority: int = 0) -> None:
        """
        注册钩子
        
        Args:
            hook_type: 钩子类型
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        if hook_type not in self._hooks:
            self._hooks[hook_type] = []
        
        handler = HookHandler(callback, priority)
        self._hooks[hook_type].append(handler)
        
        # 按优先级排序
        self._hooks[hook_type].sort(key=lambda h: h.priority, reverse=True)
        
        self._logger.debug(f"注册钩子: {hook_type.value}, 优先级: {priority}")
    
    def unregister(self, hook_type: HookType, callback: Callable[[HookContext[Any]], Any]) -> bool:
        """
        取消注册钩子
        
        Args:
            hook_type: 钩子类型
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        if hook_type not in self._hooks:
            return False
        
        original_length = len(self._hooks[hook_type])
        self._hooks[hook_type] = [h for h in self._hooks[hook_type] if h.callback != callback]
        
        if len(self._hooks[hook_type]) < original_length:
            self._logger.debug(f"取消注册钩子: {hook_type.value}")
            return True
        
        return False
    
    async def execute(self, hook_type: HookType, data: Any, config: Any = None, **kwargs: Any) -> list[Any]:
        """
        执行钩子
        
        Args:
            hook_type: 钩子类型
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        if hook_type not in self._hooks:
            return []
        
        context = HookContext(
            hook_type=hook_type,
            data=data,
            config=config,
            metadata=kwargs
        )
        
        results = []
        for handler in self._hooks[hook_type]:
            try:
                result = handler.callback(context)
                # 处理异步回调
                if hasattr(result, "__await__"):
                    result = await result
                results.append(result)
            except Exception as e:
                self._logger.error(f"执行钩子 {hook_type.value} 时出错: {e}")
        
        return results
    
    def get_registered_hooks(self, hook_type: Optional[HookType] = None) -> list[HookType]:
        """
        获取注册的钩子类型
        
        Args:
            hook_type: 钩子类型，如果为 None 则返回所有注册的钩子类型
            
        Returns:
            钩子类型列表
        """
        if hook_type:
            return [hook_type] if hook_type in self._hooks else []
        return list(self._hooks.keys())
    
    def clear(self, hook_type: Optional[HookType] = None) -> None:
        """
        清除钩子
        
        Args:
            hook_type: 钩子类型，如果为 None 则清除所有钩子
        """
        if hook_type:
            if hook_type in self._hooks:
                del self._hooks[hook_type]
                self._logger.debug(f"清除钩子: {hook_type.value}")
        else:
            self._hooks.clear()
            self._logger.debug("清除所有钩子")


# 全局钩子管理器实例
hook_manager = HookManager()


def register_hook(hook_type: HookType, priority: int = 0):
    """
    钩子注册装饰器
    
    用法:
        @register_hook(HookType.APP_STARTUP)
        def on_app_startup(context):
            pass
    """
    def decorator(func: Callable[[HookContext[Any]], Any]) -> Callable[[HookContext[Any]], Any]:
        hook_manager.register(hook_type, func, priority)
        return func
    return decorator