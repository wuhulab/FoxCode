"""
FoxCode 工作模式钩子模块

提供工作模式相关的钩子定义和操作
"""

from foxcode.core.hooks.base import HookType, hook_manager, HookContext


class WorkModeHooks:
    """工作模式钩子集合"""
    
    @staticmethod
    async def on_start(data=None, config=None, **kwargs):
        """
        工作模式开始时执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.WORK_MODE_START,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    async def on_end(data=None, config=None, **kwargs):
        """
        工作模式结束时执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.WORK_MODE_END,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    async def on_step_change(data=None, config=None, **kwargs):
        """
        工作模式步骤变化时执行
        
        Args:
            data: 钩子数据
            config: 配置
            **kwargs: 额外参数
            
        Returns:
            钩子执行结果列表
        """
        return await hook_manager.execute(
            HookType.WORK_MODE_STEP_CHANGE,
            data=data,
            config=config,
            **kwargs
        )
    
    @staticmethod
    def register_start_hook(callback, priority=0):
        """
        注册工作模式开始钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.WORK_MODE_START, callback, priority)
    
    @staticmethod
    def register_end_hook(callback, priority=0):
        """
        注册工作模式结束钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.WORK_MODE_END, callback, priority)
    
    @staticmethod
    def register_step_change_hook(callback, priority=0):
        """
        注册工作模式步骤变化钩子
        
        Args:
            callback: 回调函数
            priority: 优先级，数值越大优先级越高
        """
        hook_manager.register(HookType.WORK_MODE_STEP_CHANGE, callback, priority)
    
    @staticmethod
    def unregister_start_hook(callback):
        """
        取消注册工作模式开始钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.WORK_MODE_START, callback)
    
    @staticmethod
    def unregister_end_hook(callback):
        """
        取消注册工作模式结束钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.WORK_MODE_END, callback)
    
    @staticmethod
    def unregister_step_change_hook(callback):
        """
        取消注册工作模式步骤变化钩子
        
        Args:
            callback: 回调函数
            
        Returns:
            是否成功取消注册
        """
        return hook_manager.unregister(HookType.WORK_MODE_STEP_CHANGE, callback)