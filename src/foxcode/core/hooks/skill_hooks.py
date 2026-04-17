"""
FoxCode 技能钩子模块

提供技能生命周期相关的钩子定义和操作
"""

from foxcode.core.hooks.base import HookType, hook_manager, HookContext


class SkillHooks:
    """技能钩子集合"""
    
    @staticmethod
    async def on_pre_execute(data=None, config=None, **kwargs):
        """
        技能执行前执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.SKILL_PRE_EXECUTE,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    async def on_post_execute(data=None, config=None, **kwargs):
        """
        技能执行后执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.SKILL_POST_EXECUTE,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    async def on_error(data=None, config=None, **kwargs):
        """
        技能执行错误时执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.SKILL_ERROR,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    def register_pre_execute_hook(callback, priority=0):
        """
        注册技能执行前钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.SKILL_PRE_EXECUTE, callback, priority)
    
    @staticmethod
    def register_post_execute_hook(callback, priority=0):
        """
        注册技能执行后钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.SKILL_POST_EXECUTE, callback, priority)
    
    @staticmethod
    def register_error_hook(callback, priority=0):
        """
        注册技能执行错误钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.SKILL_ERROR, callback, priority)
    
    @staticmethod
    def unregister_pre_execute_hook(callback):
        """
        取消注册技能执行前钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.SKILL_PRE_EXECUTE, callback)
    
    @staticmethod
    def unregister_post_execute_hook(callback):
        """
        取消注册技能执行后钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.SKILL_POST_EXECUTE, callback)
    
    @staticmethod
    def unregister_error_hook(callback):
        """
        取消注册技能执行错误钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.SKILL_ERROR, callback)