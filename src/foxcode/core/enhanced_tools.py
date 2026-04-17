"""
FoxCode 增强工具模块

提供集成核心模块的工具封装，用于代理调用。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from .advanced_debugger import AdvancedDebugger
from .code_formatter import CodeFormatter
from .dependency_resolver import DependencyConfig, DependencyResolver
from .doc_generator import DocGenerator
from .error_analyzer import ErrorAnalyzer
from .git_advanced_ops import GitAdvancedOps
from .multimodal_processor import MultimodalProcessor
from .performance_analyzer import PerformanceAnalyzer, PerformanceConfig
from .project_analyzer import ProjectAnalyzer
from .refactoring_suggester import RefactoringSuggester
from .security_scanner import SecurityConfig, SecurityScanner
from .semantic_index import SemanticCodeIndex, SemanticIndexConfig
from .test_generator import TestGenerator, TestGeneratorConfig

logger = logging.getLogger(__name__)


async def search_semantic(
    query: str,
    project_path: str | None = None,
    top_k: int = 10,
) -> dict[str, Any]:
    """
    语义搜索代码
    
    Args:
        query: 自然语言查询
        project_path: 项目路径
        top_k: 返回结果数量
        
    Returns:
        搜索结果
    """
    config = SemanticIndexConfig()
    index = SemanticCodeIndex(config)

    if project_path:
        await index.index_directory(Path(project_path))

    results = await index.search(query, top_k)

    return {
        "success": True,
        "query": query,
        "results": [
            {
                "file_path": r.chunk.file_path,
                "name": r.chunk.name,
                "type": r.chunk.chunk_type,
                "score": r.score,
                "content": r.chunk.content[:500],
            }
            for r in results
        ],
    }


async def analyze_project(
    project_path: str,
    include_quality: bool = True,
) -> dict[str, Any]:
    """
    分析项目结构
    
    Args:
        project_path: 项目路径
        include_quality: 是否包含质量评分
        
    Returns:
        项目分析报告
    """
    analyzer = ProjectAnalyzer()
    report = await analyzer.analyze(Path(project_path))

    return {
        "success": True,
        "project_path": project_path,
        "tech_stack": {
            "languages": report.tech_stack.languages,
            "frameworks": report.tech_stack.frameworks,
            "databases": report.tech_stack.databases,
        },
        "structure": {
            "total_files": report.structure.total_files,
            "total_directories": report.structure.total_directories,
            "total_lines": report.structure.total_lines,
        },
        "quality_score": report.quality_score.to_dict() if include_quality else None,
        "recommendations": report.recommendations,
    }


def analyze_error(
    error_traceback: str,
    code_context: str | None = None,
) -> dict[str, Any]:
    """
    分析错误
    
    Args:
        error_traceback: 错误堆栈
        code_context: 代码上下文
        
    Returns:
        错误分析报告
    """
    analyzer = ErrorAnalyzer()
    report = analyzer.analyze_traceback(error_traceback)
    suggestions = analyzer.suggest_fix(report, code_context or "")

    return {
        "success": True,
        "error_type": report.error_type,
        "error_message": report.error_message,
        "category": report.category.value,
        "severity": report.severity.value,
        "root_cause": report.root_cause,
        "file_path": report.file_path,
        "line_number": report.line_number,
        "suggestions": [s.to_dict() for s in suggestions],
    }


async def debug_attach(
    process_id: int | None = None,
) -> dict[str, Any]:
    """
    附加调试器
    
    Args:
        process_id: 进程 ID
        
    Returns:
        调试会话信息
    """
    debugger = AdvancedDebugger()
    success = await debugger.attach(process_id)

    return {
        "success": success,
        "session_info": debugger.get_session_info(),
    }


async def profile_code(
    code: str,
    enable_memory: bool = True,
) -> dict[str, Any]:
    """
    分析代码性能
    
    Args:
        code: 代码字符串
        enable_memory: 是否启用内存分析
        
    Returns:
        性能分析报告
    """
    config = PerformanceConfig(enable_memory_profiling=enable_memory)
    analyzer = PerformanceAnalyzer(config)
    result = await analyzer.profile_code(code)

    return {
        "success": result.status.value == "completed",
        "total_time": result.total_time,
        "function_stats": [s.to_dict() for s in result.function_stats[:10]],
        "bottlenecks": [b.to_dict() for b in result.bottlenecks],
        "memory_report": result.memory_report.to_dict() if result.memory_report else None,
        "error": result.error,
    }


async def scan_security(
    target_path: str,
    check_dependencies: bool = True,
) -> dict[str, Any]:
    """
    扫描安全漏洞
    
    Args:
        target_path: 目标路径
        check_dependencies: 是否检查依赖
        
    Returns:
        安全扫描报告
    """
    config = SecurityConfig(check_dependencies=check_dependencies)
    scanner = SecurityScanner(config)
    report = await scanner.scan_directory(Path(target_path))

    return {
        "success": True,
        "project_path": report.project_path,
        "files_scanned": report.files_scanned,
        "issues": [i.to_dict() for i in report.issues],
        "secrets": [s.to_dict() for s in report.secrets],
        "dependency_issues": [d.to_dict() for d in report.dependency_issues],
        "summary": report.summary,
    }


async def format_code(
    file_path: str,
    language: str | None = None,
) -> dict[str, Any]:
    """
    格式化代码
    
    Args:
        file_path: 文件路径
        language: 语言（可选）
        
    Returns:
        格式化结果
    """
    formatter = CodeFormatter()
    result = await formatter.format_file(Path(file_path))

    return result.to_dict()


def suggest_refactoring(
    file_path: str,
) -> dict[str, Any]:
    """
    重构建议
    
    Args:
        file_path: 文件路径
        
    Returns:
        重构建议报告
    """
    suggester = RefactoringSuggester()
    report = suggester.analyze_file(Path(file_path))

    return {
        "success": True,
        "file_path": report.file_path,
        "smells": [s.to_dict() for s in report.smells],
        "pattern_suggestions": [p.to_dict() for p in report.pattern_suggestions],
        "refactoring_actions": [a.to_dict() for a in report.refactoring_actions],
        "complexity_score": report.complexity_score,
        "maintainability_index": report.maintainability_index,
    }


async def analyze_dependencies(
    project_path: str,
    check_outdated: bool = True,
) -> dict[str, Any]:
    """
    分析依赖关系
    
    Args:
        project_path: 项目路径
        check_outdated: 是否检查过时依赖
        
    Returns:
        依赖分析报告
    """
    config = DependencyConfig(check_outdated=check_outdated)
    resolver = DependencyResolver(config)
    report = await resolver.resolve_project(Path(project_path))

    return {
        "success": True,
        "project_path": report.project_path,
        "language": report.language.value,
        "dependencies": [d.to_dict() for d in report.dependencies],
        "conflicts": [c.to_dict() for c in report.conflicts],
        "outdated": [o.to_dict() for o in report.outdated],
        "summary": {
            "total_count": report.total_count,
            "production_count": report.production_count,
            "development_count": report.development_count,
        },
    }


async def generate_tests(
    source_file: str,
    include_edge_cases: bool = True,
    include_exceptions: bool = True,
) -> dict[str, Any]:
    """
    生成测试用例
    
    Args:
        source_file: 源文件路径
        include_edge_cases: 是否包含边界测试
        include_exceptions: 是否包含异常测试
        
    Returns:
        测试生成结果
    """
    config = TestGeneratorConfig(
        generate_edge_cases=include_edge_cases,
        generate_exception_tests=include_exceptions,
    )
    generator = TestGenerator(config)
    result = await generator.generate_tests(Path(source_file))

    return {
        "success": True,
        "source_file": result.source_file,
        "test_file": result.test_file,
        "test_cases": [tc.to_code() for tc in result.test_cases],
        "imports": result.imports,
        "fixtures": result.fixtures,
        "coverage_estimate": result.coverage_estimate,
    }


async def generate_docs(
    source_path: str,
    doc_type: str = "api",
) -> dict[str, Any]:
    """
    生成文档
    
    Args:
        source_path: 源路径
        doc_type: 文档类型 (api, readme, docstring)
        
    Returns:
        文档生成结果
    """
    generator = DocGenerator()

    if doc_type == "api":
        result = await generator.generate_api_docs(Path(source_path))
    elif doc_type == "readme":
        result = await generator.generate_readme(Path(source_path))
    else:
        result = await generator.generate_docstrings(Path(source_path))

    return {
        "success": True,
        "doc_type": doc_type,
        "content": result.content if hasattr(result, "content") else str(result),
    }


async def git_advanced(
    operation: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Git 高级操作
    
    Args:
        operation: 操作类型 (commit, branch, conflict, log)
        **kwargs: 操作参数
        
    Returns:
        操作结果
    """
    git_ops = GitAdvancedOps()

    if operation == "commit":
        message = await git_ops.generate_commit_message(kwargs.get("diff", ""))
        return {"success": True, "suggested_message": message}
    elif operation == "branch":
        branches = await git_ops.list_branches()
        return {"success": True, "branches": branches}
    elif operation == "conflict":
        conflicts = await git_ops.analyze_conflicts()
        return {"success": True, "conflicts": conflicts}
    else:
        return {"success": False, "error": f"未知操作: {operation}"}


async def analyze_image(
    image_path: str | None = None,
    image_base64: str | None = None,
) -> dict[str, Any]:
    """
    分析图像
    
    Args:
        image_path: 图像路径
        image_base64: Base64 编码的图像
        
    Returns:
        图像分析结果
    """
    processor = MultimodalProcessor()

    result = await processor.analyze_image(
        image_path=Path(image_path) if image_path else None,
        image_base64=image_base64,
    )

    return result.to_dict()


def generate_diagram(
    structure: dict[str, Any],
    diagram_type: str = "architecture",
    format: str = "mermaid",
) -> dict[str, Any]:
    """
    生成图表
    
    Args:
        structure: 结构数据
        diagram_type: 图表类型
        format: 格式 (mermaid, plantuml)
        
    Returns:
        图表生成结果
    """
    from .multimodal_processor import DiagramType

    processor = MultimodalProcessor()

    diagram_type_enum = DiagramType(diagram_type) if diagram_type in [e.value for e in DiagramType] else DiagramType.ARCHITECTURE

    result = processor.generate_architecture_diagram(structure, diagram_type_enum, format)

    return result.to_dict()


async def execute_snippet(
    code: str,
    language: str = "python",
    timeout: int = 30,
) -> dict[str, Any]:
    """
    执行代码片段
    
    Args:
        code: 代码片段
        language: 语言
        timeout: 超时时间
        
    Returns:
        执行结果
    """
    if language != "python":
        return {
            "success": False,
            "error": f"不支持的语言: {language}",
        }

    try:
        # 创建安全的执行环境
        safe_globals = {
            "__builtins__": {
                "print": print,
                "len": len,
                "range": range,
                "list": list,
                "dict": dict,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "None": None,
                "True": True,
                "False": False,
            }
        }

        # 使用 asyncio 执行并设置超时
        async def run_code():
            local_vars = {}
            exec(code, safe_globals, local_vars)
            return local_vars

        result_vars = await asyncio.wait_for(run_code(), timeout=timeout)

        return {
            "success": True,
            "output": str(result_vars),
            "variables": {k: repr(v) for k, v in result_vars.items()},
        }

    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": f"执行超时 ({timeout}秒)",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}",
        }


# 工具注册表
ENHANCED_TOOLS = {
    "search_semantic": {
        "function": search_semantic,
        "description": "语义搜索代码，支持自然语言查询",
        "parameters": {
            "query": {"type": "string", "description": "自然语言查询"},
            "project_path": {"type": "string", "description": "项目路径", "default": None},
            "top_k": {"type": "integer", "description": "返回结果数量", "default": 10},
        },
    },
    "analyze_project": {
        "function": analyze_project,
        "description": "分析项目结构、技术栈和代码质量",
        "parameters": {
            "project_path": {"type": "string", "description": "项目路径"},
            "include_quality": {"type": "boolean", "description": "是否包含质量评分", "default": True},
        },
    },
    "analyze_error": {
        "function": analyze_error,
        "description": "分析错误堆栈，提供修复建议",
        "parameters": {
            "error_traceback": {"type": "string", "description": "错误堆栈"},
            "code_context": {"type": "string", "description": "代码上下文", "default": None},
        },
    },
    "debug_attach": {
        "function": debug_attach,
        "description": "附加调试器到进程",
        "parameters": {
            "process_id": {"type": "integer", "description": "进程 ID", "default": None},
        },
    },
    "profile_code": {
        "function": profile_code,
        "description": "分析代码性能，识别瓶颈",
        "parameters": {
            "code": {"type": "string", "description": "代码字符串"},
            "enable_memory": {"type": "boolean", "description": "是否启用内存分析", "default": True},
        },
    },
    "scan_security": {
        "function": scan_security,
        "description": "扫描代码安全漏洞",
        "parameters": {
            "target_path": {"type": "string", "description": "目标路径"},
            "check_dependencies": {"type": "boolean", "description": "是否检查依赖", "default": True},
        },
    },
    "format_code": {
        "function": format_code,
        "description": "格式化代码",
        "parameters": {
            "file_path": {"type": "string", "description": "文件路径"},
            "language": {"type": "string", "description": "语言", "default": None},
        },
    },
    "suggest_refactoring": {
        "function": suggest_refactoring,
        "description": "提供重构建议",
        "parameters": {
            "file_path": {"type": "string", "description": "文件路径"},
        },
    },
    "analyze_dependencies": {
        "function": analyze_dependencies,
        "description": "分析项目依赖关系",
        "parameters": {
            "project_path": {"type": "string", "description": "项目路径"},
            "check_outdated": {"type": "boolean", "description": "是否检查过时依赖", "default": True},
        },
    },
    "generate_tests": {
        "function": generate_tests,
        "description": "自动生成测试用例",
        "parameters": {
            "source_file": {"type": "string", "description": "源文件路径"},
            "include_edge_cases": {"type": "boolean", "description": "是否包含边界测试", "default": True},
            "include_exceptions": {"type": "boolean", "description": "是否包含异常测试", "default": True},
        },
    },
    "generate_docs": {
        "function": generate_docs,
        "description": "自动生成文档",
        "parameters": {
            "source_path": {"type": "string", "description": "源路径"},
            "doc_type": {"type": "string", "description": "文档类型", "default": "api"},
        },
    },
    "git_advanced": {
        "function": git_advanced,
        "description": "Git 高级操作",
        "parameters": {
            "operation": {"type": "string", "description": "操作类型"},
        },
    },
    "analyze_image": {
        "function": analyze_image,
        "description": "分析图像内容",
        "parameters": {
            "image_path": {"type": "string", "description": "图像路径", "default": None},
            "image_base64": {"type": "string", "description": "Base64 编码的图像", "default": None},
        },
    },
    "generate_diagram": {
        "function": generate_diagram,
        "description": "生成架构图或流程图",
        "parameters": {
            "structure": {"type": "object", "description": "结构数据"},
            "diagram_type": {"type": "string", "description": "图表类型", "default": "architecture"},
            "format": {"type": "string", "description": "格式", "default": "mermaid"},
        },
    },
    "execute_snippet": {
        "function": execute_snippet,
        "description": "执行代码片段",
        "parameters": {
            "code": {"type": "string", "description": "代码片段"},
            "language": {"type": "string", "description": "语言", "default": "python"},
            "timeout": {"type": "integer", "description": "超时时间", "default": 30},
        },
    },
}


def get_enhanced_tools() -> dict[str, Any]:
    """获取增强工具列表"""
    return ENHANCED_TOOLS
