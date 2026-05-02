"""
FoxCode 会话钩子模块 - 会话生命周期事件钩子

这个文件提供会话管理相关的钩子:
- on_start: 会话开始时触发
- on_end: 会话结束时触发
- on_save: 会话保存时触发

使用方式:
    from foxcode.core.hooks.session_hooks import SessionHooks

    results = await SessionHooks.on_start(data={"session_id": "xxx"})
"""

from foxcode.core.hooks.base import HookType, hook_manager, HookContext


class SessionHooks:
    """会话钩子集合"""
    
    @staticmethod
    async def on_start(data=None, config=None, **kwargs):
        """
        会话开始时执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.SESSION_START,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    async def on_end(data=None, config=None, **kwargs):
        """
        会话结束时执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.SESSION_END,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    async def on_save(data=None, config=None, **kwargs):
        """
        会话保存时执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.SESSION_SAVE,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    def register_start_hook(callback, priority=0):
        """
        注册会话开始钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.SESSION_START, callback, priority)
    
    @staticmethod
    def register_end_hook(callback, priority=0):
        """
        注册会话结束钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.SESSION_END, callback, priority)
    
    @staticmethod
    def register_save_hook(callback, priority=0):
        """
        注册会话保存钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.SESSION_SAVE, callback, priority)
    
    @staticmethod
    def unregister_start_hook(callback):
        """
        取消注册会话开始钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.SESSION_START, callback)
    
    @staticmethod
    def unregister_end_hook(callback):
        """
        取消注册会话结束钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.SESSION_END, callback)
    
    @staticmethod
    def unregister_save_hook(callback):
        """
        取消注册会话保存钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.SESSION_SAVE, callback)