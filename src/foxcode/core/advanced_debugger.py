"""
FoxCode 高级调试器集成

提供断点管理、变量监视、调用栈分析等调试功能。
支持 Python 调试器（pdb/debugpy）集成。

主要功能：
- 断点管理（条件断点、日志断点）
- 变量监视和表达式求值
- 调用栈分析和栈帧切换
- Python 调试器集成
"""

from __future__ import annotations

import ast
import logging
import pdb
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# 安全表达式求值相关常量
MAX_EXPRESSION_LENGTH = 1000  # 表达式最大长度
FORBIDDEN_NODES = {
    ast.Import, ast.ImportFrom,  # 禁止导入
    ast.Global,  # 禁止全局声明
    ast.AsyncFunctionDef, ast.FunctionDef,  # 禁止定义函数
    ast.ClassDef,  # 禁止定义类
}
# Python 3.12+ 移除了 ast.Exec，兼容处理
if hasattr(ast, 'Exec'):
    FORBIDDEN_NODES.add(ast.Exec)
FORBIDDEN_NAMES = {
    '__import__', 'eval', 'exec', 'compile', 'open',
    'input', 'breakpoint', 'globals', 'locals',
    'vars', 'dir', 'getattr', 'setattr', 'delattr',
    'hasattr', '__builtins__', '__class__', '__base__',
    '__subclasses__', '__mro__', '__globals__',
    'os', 'sys', 'subprocess', 'socket', 'pickle',
    'marshal', 'shelve', 'importlib', 'ctypes',
}


def _validate_expression(expression: str) -> bool:
    """
    验证表达式是否安全
    
    Args:
        expression: 要验证的表达式字符串
        
    Returns:
        表达式是否安全
    """
    # 检查长度
    if len(expression) > MAX_EXPRESSION_LENGTH:
        return False

    try:
        # 解析表达式为 AST
        tree = ast.parse(expression, mode='eval')

        # 遍历 AST 检查危险节点
        for node in ast.walk(tree):
            # 检查禁止的节点类型
            if type(node) in FORBIDDEN_NODES:
                return False

            # 检查属性访问
            if isinstance(node, ast.Attribute):
                if node.attr.startswith('_'):
                    return False

            # 检查名称
            if isinstance(node, ast.Name):
                if node.id in FORBIDDEN_NAMES:
                    return False

        return True
    except SyntaxError:
        return False


def safe_eval(expression: str, globals_dict: dict[str, Any], locals_dict: dict[str, Any]) -> tuple[Any, str | None]:
    """
    安全地求值表达式
    
    Args:
        expression: 表达式字符串
        globals_dict: 全局变量字典
        locals_dict: 局部变量字典
        
    Returns:
        (求值结果, 错误信息) 元组，成功时错误信息为 None
    """
    # 验证表达式安全性
    if not _validate_expression(expression):
        return None, "表达式包含不安全的操作"

    try:
        # 创建受限的全局命名空间
        safe_globals = {
            '__builtins__': {
                'abs': abs, 'all': all, 'any': any, 'bin': bin,
                'bool': bool, 'chr': chr, 'complex': complex,
                'dict': dict, 'divmod': divmod, 'enumerate': enumerate,
                'filter': filter, 'float': float, 'format': format,
                'frozenset': frozenset, 'hex': hex, 'int': int,
                'isinstance': isinstance, 'issubclass': issubclass,
                'iter': iter, 'len': len, 'list': list, 'map': map,
                'max': max, 'min': min, 'next': next, 'oct': oct,
                'ord': ord, 'pow': pow, 'print': print, 'range': range,
                'repr': repr, 'reversed': reversed, 'round': round,
                'set': set, 'slice': slice, 'sorted': sorted,
                'str': str, 'sum': sum, 'tuple': tuple, 'type': type,
                'zip': zip, 'True': True, 'False': False, 'None': None,
            }
        }

        # 合并用户提供的全局变量（过滤危险名称）
        for key, value in globals_dict.items():
            if key not in FORBIDDEN_NAMES and not key.startswith('_'):
                safe_globals[key] = value

        # 执行求值
        result = eval(expression, safe_globals, locals_dict)
        return result, None

    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)}"


class BreakpointType(str, Enum):
    """断点类型"""
    LINE = "line"               # 行断点
    CONDITIONAL = "conditional"  # 条件断点
    LOG = "log"                 # 日志断点
    FUNCTION = "function"       # 函数断点
    EXCEPTION = "exception"     # 异常断点


class DebugState(str, Enum):
    """调试状态"""
    IDLE = "idle"               # 空闲
    RUNNING = "running"         # 运行中
    PAUSED = "paused"           # 已暂停
    STEPPING = "stepping"       # 单步执行
    STOPPED = "stopped"         # 已停止


class StopReason(str, Enum):
    """停止原因"""
    BREAKPOINT = "breakpoint"   # 断点
    STEP = "step"               # 单步
    EXCEPTION = "exception"     # 异常
    PAUSE = "pause"             # 手动暂停
    ENTRY = "entry"             # 入口


@dataclass
class Breakpoint:
    """
    断点
    
    Attributes:
        id: 断点 ID
        file_path: 文件路径
        line_number: 行号
        type: 断点类型
        condition: 条件表达式
        log_message: 日志消息
        hit_count: 命中次数
        enabled: 是否启用
        temporary: 是否临时断点
    """
    id: str
    file_path: str
    line_number: int
    type: BreakpointType = BreakpointType.LINE
    condition: str = ""
    log_message: str = ""
    hit_count: int = 0
    enabled: bool = True
    temporary: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "type": self.type.value,
            "condition": self.condition,
            "log_message": self.log_message,
            "hit_count": self.hit_count,
            "enabled": self.enabled,
            "temporary": self.temporary,
        }


@dataclass
class StackFrame:
    """
    堆栈帧
    
    Attributes:
        id: 帧 ID
        file_path: 文件路径
        line_number: 行号
        function_name: 函数名
        module_name: 模块名
        code_line: 代码行
        locals: 局部变量
    """
    id: int
    file_path: str
    line_number: int
    function_name: str
    module_name: str = ""
    code_line: str = ""
    locals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "function_name": self.function_name,
            "module_name": self.module_name,
            "code_line": self.code_line,
            "locals": {k: repr(v) for k, v in self.locals.items()},
        }


@dataclass
class Variable:
    """
    变量
    
    Attributes:
        name: 变量名
        value: 值
        type: 类型
        is_expandable: 是否可展开
        children: 子变量
    """
    name: str
    value: Any
    type: str = ""
    is_expandable: bool = False
    children: list[Variable] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": repr(self.value),
            "type": self.type,
            "is_expandable": self.is_expandable,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class EvaluationResult:
    """
    表达式求值结果
    
    Attributes:
        expression: 表达式
        result: 结果
        error: 错误信息
        type: 结果类型
    """
    expression: str
    result: Any = None
    error: str = ""
    type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "expression": self.expression,
            "result": repr(self.result) if self.result is not None else None,
            "error": self.error,
            "type": self.type,
        }


@dataclass
class DebugSession:
    """
    调试会话
    
    Attributes:
        id: 会话 ID
        state: 调试状态
        current_frame: 当前帧 ID
        breakpoints: 断点列表
        call_stack: 调用栈
        watches: 监视表达式
        started_at: 开始时间
    """
    id: str
    state: DebugState = DebugState.IDLE
    current_frame: int = 0
    breakpoints: list[Breakpoint] = field(default_factory=list)
    call_stack: list[StackFrame] = field(default_factory=list)
    watches: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state.value,
            "current_frame": self.current_frame,
            "breakpoints": [b.to_dict() for b in self.breakpoints],
            "call_stack": [f.to_dict() for f in self.call_stack],
            "watches": self.watches,
            "started_at": self.started_at.isoformat(),
        }


class DebuggerConfig(BaseModel):
    """
    调试器配置
    
    Attributes:
        auto_start: 是否自动启动
        stop_on_entry: 是否在入口停止
        stop_on_exception: 是否在异常停止
        max_stack_frames: 最大堆栈帧数
        timeout: 超时时间（秒）
    """
    auto_start: bool = False
    stop_on_entry: bool = False
    stop_on_exception: bool = True
    max_stack_frames: int = Field(default=100, ge=10)
    timeout: int = Field(default=300, ge=10)


class AdvancedDebugger:
    """
    高级调试器集成
    
    提供断点管理、变量监视、调用栈分析等调试功能。
    
    Example:
        >>> debugger = AdvancedDebugger()
        >>> bp = debugger.set_breakpoint(Path("main.py"), 10)
        >>> await debugger.attach()
        >>> await debugger.continue_execution()
    """

    def __init__(self, config: DebuggerConfig | None = None):
        """
        初始化调试器
        
        Args:
            config: 调试器配置
        """
        self.config = config or DebuggerConfig()
        self._session: DebugSession | None = None
        self._breakpoint_counter = 0
        self._frame_counter = 0
        self._pdb: pdb.Pdb | None = None
        self._tracing = False
        self._stop_event = threading.Event()
        logger.info("高级调试器初始化完成")

    def _generate_breakpoint_id(self) -> str:
        """生成断点 ID"""
        self._breakpoint_counter += 1
        return f"bp-{self._breakpoint_counter:04d}"

    def _generate_frame_id(self) -> int:
        """生成帧 ID"""
        self._frame_counter += 1
        return self._frame_counter

    async def attach(self, process_id: int | None = None) -> bool:
        """
        附加到进程
        
        Args:
            process_id: 进程 ID（当前仅支持当前进程）
            
        Returns:
            是否成功
        """
        if self._session is not None:
            logger.warning("调试会话已存在")
            return False

        # 创建新会话
        session_id = f"debug-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self._session = DebugSession(id=session_id, state=DebugState.RUNNING)

        # 设置跟踪函数
        if self.config.stop_on_entry:
            self._set_trace()

        logger.info(f"调试会话已创建: {session_id}")
        return True

    def _set_trace(self) -> None:
        """设置跟踪"""
        self._tracing = True
        self._pdb = pdb.Pdb()
        sys.settrace(self._trace_func)

    def _trace_func(self, frame, event, arg) -> Callable | None:
        """跟踪函数"""
        if not self._tracing:
            return None

        # 检查断点
        if event == "line":
            file_path = frame.f_code.co_filename
            line_number = frame.f_lineno

            for bp in (self._session.breakpoints if self._session else []):
                if (bp.enabled and
                    bp.file_path == file_path and
                    bp.line_number == line_number):

                    # 检查条件
                    if bp.condition:
                        try:
                            # 使用安全求值函数替代直接 eval
                            result, error = safe_eval(bp.condition, frame.f_globals, frame.f_locals)
                            if error:
                                logger.warning(f"断点条件求值失败: {error}")
                                return self._trace_func
                            if not result:
                                return self._trace_func
                        except Exception as e:
                            logger.warning(f"断点条件求值异常: {e}")
                            return self._trace_func

                    # 命中断点
                    bp.hit_count += 1

                    if bp.type == BreakpointType.LOG:
                        # 日志断点
                        print(f"[LOG] {bp.log_message}")
                    else:
                        # 暂停执行
                        self._session.state = DebugState.PAUSED
                        self._update_call_stack(frame)
                        self._stop_event.set()
                        return None

        return self._trace_func

    def _update_call_stack(self, current_frame) -> None:
        """更新调用栈"""
        if not self._session:
            return

        self._session.call_stack = []
        frame = current_frame
        frame_id = 0

        while frame and frame_id < self.config.max_stack_frames:
            # 获取代码行
            code_line = ""
            try:
                with open(frame.f_code.co_filename, encoding="utf-8") as f:
                    lines = f.readlines()
                    if frame.f_lineno <= len(lines):
                        code_line = lines[frame.f_lineno - 1].strip()
            except Exception:
                pass

            stack_frame = StackFrame(
                id=self._generate_frame_id(),
                file_path=frame.f_code.co_filename,
                line_number=frame.f_lineno,
                function_name=frame.f_code.co_name,
                module_name=frame.f_globals.get("__name__", ""),
                code_line=code_line,
                locals=dict(frame.f_locals),
            )
            self._session.call_stack.append(stack_frame)
            frame = frame.f_back
            frame_id += 1

    def set_breakpoint(
        self,
        file_path: Path,
        line: int,
        condition: str | None = None,
        log_message: str | None = None,
    ) -> Breakpoint:
        """
        设置断点
        
        Args:
            file_path: 文件路径
            line: 行号
            condition: 条件表达式
            log_message: 日志消息
            
        Returns:
            断点对象
        """
        bp_type = BreakpointType.LINE
        if condition:
            bp_type = BreakpointType.CONDITIONAL
        elif log_message:
            bp_type = BreakpointType.LOG

        bp = Breakpoint(
            id=self._generate_breakpoint_id(),
            file_path=str(file_path),
            line_number=line,
            type=bp_type,
            condition=condition or "",
            log_message=log_message or "",
        )

        if self._session:
            self._session.breakpoints.append(bp)

        logger.debug(f"设置断点: {bp.id} at {file_path}:{line}")
        return bp

    def remove_breakpoint(self, breakpoint_id: str) -> bool:
        """
        移除断点
        
        Args:
            breakpoint_id: 断点 ID
            
        Returns:
            是否成功
        """
        if not self._session:
            return False

        for i, bp in enumerate(self._session.breakpoints):
            if bp.id == breakpoint_id:
                self._session.breakpoints.pop(i)
                logger.debug(f"移除断点: {breakpoint_id}")
                return True

        return False

    def list_breakpoints(self) -> list[Breakpoint]:
        """
        列出所有断点
        
        Returns:
            断点列表
        """
        if not self._session:
            return []
        return list(self._session.breakpoints)

    def enable_breakpoint(self, breakpoint_id: str, enabled: bool = True) -> bool:
        """
        启用/禁用断点
        
        Args:
            breakpoint_id: 断点 ID
            enabled: 是否启用
            
        Returns:
            是否成功
        """
        if not self._session:
            return False

        for bp in self._session.breakpoints:
            if bp.id == breakpoint_id:
                bp.enabled = enabled
                return True

        return False

    async def continue_execution(self) -> StopReason:
        """
        继续执行
        
        Returns:
            停止原因
        """
        if not self._session:
            return StopReason.STOPPED

        self._session.state = DebugState.RUNNING
        self._stop_event.clear()

        # 等待停止事件或超时
        if self._stop_event.wait(timeout=self.config.timeout):
            return StopReason.BREAKPOINT

        return StopReason.STOPPED

    async def step_over(self) -> StopReason:
        """
        单步跳过
        
        Returns:
            停止原因
        """
        if not self._session or not self._pdb:
            return StopReason.STOPPED

        self._session.state = DebugState.STEPPING

        # 执行单步
        try:
            if self._pdb:
                self._pdb.set_next(self._get_current_frame())
        except Exception as e:
            logger.error(f"单步执行失败: {e}")

        return StopReason.STEP

    async def step_into(self) -> StopReason:
        """
        单步进入
        
        Returns:
            停止原因
        """
        if not self._session or not self._pdb:
            return StopReason.STOPPED

        self._session.state = DebugState.STEPPING

        try:
            if self._pdb:
                self._pdb.set_step()
        except Exception as e:
            logger.error(f"单步执行失败: {e}")

        return StopReason.STEP

    async def step_out(self) -> StopReason:
        """
        单步跳出
        
        Returns:
            停止原因
        """
        if not self._session or not self._pdb:
            return StopReason.STOPPED

        self._session.state = DebugState.STEPPING

        try:
            if self._pdb:
                self._pdb.set_return(self._get_current_frame())
        except Exception as e:
            logger.error(f"单步执行失败: {e}")

        return StopReason.STEP

    def _get_current_frame(self):
        """获取当前帧"""
        if not self._session or not self._session.call_stack:
            return None

        # 返回最底层的帧
        return sys._getframe(0)

    def get_call_stack(self) -> list[StackFrame]:
        """
        获取调用栈
        
        Returns:
            调用栈列表
        """
        if not self._session:
            return []
        return list(self._session.call_stack)

    def get_variables(self, frame_id: int | None = None) -> dict[str, Variable]:
        """
        获取变量
        
        Args:
            frame_id: 帧 ID（None 表示当前帧）
            
        Returns:
            变量字典
        """
        if not self._session:
            return {}

        frame = None
        if frame_id is not None:
            for f in self._session.call_stack:
                if f.id == frame_id:
                    frame = f
                    break
        else:
            frame = self._session.call_stack[0] if self._session.call_stack else None

        if not frame:
            return {}

        variables = {}
        for name, value in frame.locals.items():
            var = Variable(
                name=name,
                value=value,
                type=type(value).__name__,
                is_expandable=hasattr(value, "__dict__") or isinstance(value, (list, dict, tuple, set)),
            )
            variables[name] = var

        return variables

    def evaluate_expression(
        self,
        expression: str,
        frame_id: int | None = None,
    ) -> EvaluationResult:
        """
        求值表达式
        
        Args:
            expression: 表达式
            frame_id: 帧 ID
            
        Returns:
            求值结果
        """
        if not self._session:
            return EvaluationResult(expression=expression, error="无活动调试会话")

        frame = None
        if frame_id is not None:
            for f in self._session.call_stack:
                if f.id == frame_id:
                    frame = f
                    break
        else:
            frame = self._session.call_stack[0] if self._session.call_stack else None

        if not frame:
            return EvaluationResult(expression=expression, error="找不到指定的栈帧")

        try:
            # 获取帧的全局和局部变量
            globals_dict = {}
            locals_dict = dict(frame.locals)

            # 使用安全求值函数
            result, error = safe_eval(expression, globals_dict, locals_dict)
            if error:
                return EvaluationResult(
                    expression=expression,
                    error=error,
                )
            return EvaluationResult(
                expression=expression,
                result=result,
                type=type(result).__name__,
            )
        except Exception as e:
            return EvaluationResult(
                expression=expression,
                error=f"{type(e).__name__}: {str(e)}",
            )

    def set_variable(self, name: str, value: str, frame_id: int | None = None) -> bool:
        """
        设置变量值
        
        Args:
            name: 变量名
            value: 值表达式
            frame_id: 帧 ID
            
        Returns:
            是否成功
        """
        if not self._session:
            return False

        frame = None
        if frame_id is not None:
            for f in self._session.call_stack:
                if f.id == frame_id:
                    frame = f
                    break
        else:
            frame = self._session.call_stack[0] if self._session.call_stack else None

        if not frame:
            return False

        try:
            # 使用安全求值函数
            evaluated, error = safe_eval(value, {}, dict(frame.locals))
            if error:
                logger.error(f"设置变量失败: {error}")
                return False
            frame.locals[name] = evaluated
            return True
        except Exception as e:
            logger.error(f"设置变量失败: {e}")
            return False

    def add_watch(self, expression: str) -> bool:
        """
        添加监视表达式
        
        Args:
            expression: 表达式
            
        Returns:
            是否成功
        """
        if not self._session:
            return False

        if expression not in self._session.watches:
            self._session.watches.append(expression)

        return True

    def remove_watch(self, expression: str) -> bool:
        """
        移除监视表达式
        
        Args:
            expression: 表达式
            
        Returns:
            是否成功
        """
        if not self._session:
            return False

        try:
            self._session.watches.remove(expression)
            return True
        except ValueError:
            return False

    def get_watches(self) -> list[EvaluationResult]:
        """
        获取所有监视表达式的值
        
        Returns:
            求值结果列表
        """
        if not self._session:
            return []

        return [self.evaluate_expression(expr) for expr in self._session.watches]

    async def detach(self) -> bool:
        """
        分离调试器
        
        Returns:
            是否成功
        """
        if not self._session:
            return False

        # 停止跟踪
        self._tracing = False
        sys.settrace(None)

        self._session.state = DebugState.STOPPED
        self._session = None
        self._pdb = None

        logger.info("调试会话已结束")
        return True

    def get_state(self) -> DebugState:
        """
        获取调试状态
        
        Returns:
            调试状态
        """
        if not self._session:
            return DebugState.IDLE
        return self._session.state

    def get_session_info(self) -> dict[str, Any] | None:
        """
        获取会话信息
        
        Returns:
            会话信息
        """
        if not self._session:
            return None
        return self._session.to_dict()


# 创建默认调试器实例
advanced_debugger = AdvancedDebugger()
