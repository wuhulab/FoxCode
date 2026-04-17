"""
FoxCode 服务钩子模块

提供服务相关的钩子定义和操作
"""

from foxcode.core.hooks.base import HookType, hook_manager, HookContext


class ServiceHooks:
    """服务钩子集合"""
    
    @staticmethod
    async def on_start(data=None, config=None, **kwargs):
        """
        服务启动时执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.SERVICE_START,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    async def on_stop(data=None, config=None, **kwargs):
        """
        服务停止时执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.SERVICE_STOP,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    def register_start_hook(callback, priority=0):
        """
        注册服务启动钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.SERVICE_START, callback, priority)
    
    @staticmethod
    def register_stop_hook(callback, priority=0):
        """
        注册服务停止钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.SERVICE_STOP, callback, priority)
    
    @staticmethod
    def unregister_start_hook(callback):
        """
        取消注册服务启动钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.SERVICE_START, callback)
    
    @staticmethod
    def unregister_stop_hook(callback):
        """
        取消注册服务停止钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.SERVICE_STOP, callback)