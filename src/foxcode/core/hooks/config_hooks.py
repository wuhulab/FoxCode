"""
FoxCode 配置钩子模块

提供配置相关的钩子定义和操作
"""

from foxcode.core.hooks.base import HookType, hook_manager, HookContext


class ConfigHooks:
    """配置钩子集合"""
    
    @staticmethod
    async def on_loaded(data=None, config=None, **kwargs):
        """
        配置加载后执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.CONFIG_LOADED,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    async def on_updated(data=None, config=None, **kwargs):
        """
        配置更新后执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.CONFIG_UPDATED,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    def register_loaded_hook(callback, priority=0):
        """
        注册配置加载后钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.CONFIG_LOADED, callback, priority)
    
    @staticmethod
    def register_updated_hook(callback, priority=0):
        """
        注册配置更新后钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.CONFIG_UPDATED, callback, priority)
    
    @staticmethod
    def unregister_loaded_hook(callback):
        """
        取消注册配置加载后钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.CONFIG_LOADED, callback)
    
    @staticmethod
    def unregister_updated_hook(callback):
        """
        取消注册配置更新后钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.CONFIG_UPDATED, callback)