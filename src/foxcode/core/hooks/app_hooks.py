"""
FoxCode 应用钩子模块 - 应用生命周期事件钩子

这个文件提供应用级别的生命周期钩子:
- on_startup: 应用启动时触发
- on_shutdown: 应用关闭时触发

使用方式:
    from foxcode.core.hooks.app_hooks import AppHooks

    results = await AppHooks.on_startup(config=config)
"""

from foxcode.core.hooks.base import HookType, hook_manager, HookContext


class AppHooks:
    """应用钩子集合"""
    
    @staticmethod
    async def on_startup(data=None, config=None, **kwargs):
        """
        应用启动时执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.APP_STARTUP,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    async def on_shutdown(data=None, config=None, **kwargs):
        """
        应用关闭时执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.APP_SHUTDOWN,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    def register_startup_hook(callback, priority=0):
        """
        注册应用启动钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.APP_STARTUP, callback, priority)
    
    @staticmethod
    def register_shutdown_hook(callback, priority=0):
        """
        注册应用关闭钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.APP_SHUTDOWN, callback, priority)
    
    @staticmethod
    def unregister_startup_hook(callback):
        """
        取消注册应用启动钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.APP_STARTUP, callback)
    
    @staticmethod
    def unregister_shutdown_hook(callback):
        """
        取消注册应用关闭钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.APP_SHUTDOWN, callback)