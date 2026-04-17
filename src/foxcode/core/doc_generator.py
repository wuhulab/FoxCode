"""
FoxCode 文档自动生成器

提供 API 文档、代码注释和 README 自动生成功能。

主要功能：
- API 文档生成（OpenAPI/Swagger）
- 代码注释生成（docstring）
- README 自动生成
- 多种文档格式支持
"""

from __future__ import annotations

import ast
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DocFormat(str, Enum):
    """文档格式"""
    MARKDOWN = "markdown"
    RST = "rst"
    HTML = "html"
    OPENAPI = "openapi"
    SWAGGER = "swagger"


class DocStyle(str, Enum):
    """文档风格"""
    GOOGLE = "google"       # Google 风格
    NUMPY = "numpy"         # NumPy 风格
    SPHINX = "sphinx"       # Sphinx 风格
    REST = "rest"           # reStructuredText


@dataclass
class APIEndpoint:
    """
    API 端点
    
    Attributes:
        path: 路径
        method: HTTP 方法
        summary: 摘要
        description: 描述
        parameters: 参数列表
        request_body: 请求体
        responses: 响应
        tags: 标签
    """
    path: str
    method: str = "GET"
    summary: str = ""
    description: str = ""
    parameters: list[dict[str, Any]] = field(default_factory=list)
    request_body: dict[str, Any] = field(default_factory=dict)
    responses: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_openapi(self) -> dict[str, Any]:
        """转换为 OpenAPI 格式"""
        endpoint = {
            "summary": self.summary,
            "description": self.description,
            "parameters": self.parameters,
            "responses": self.responses,
            "tags": self.tags,
        }

        if self.request_body:
            endpoint["requestBody"] = self.request_body

        return endpoint


@dataclass
class DocGenerationResult:
    """
    文档生成结果
    
    Attributes:
        success: 是否成功
        format: 文档格式
        content: 文档内容
        file_path: 输出文件路径
        endpoints: API 端点列表
        error: 错误信息
    """
    success: bool = True
    format: DocFormat = DocFormat.MARKDOWN
    content: str = ""
    file_path: str = ""
    endpoints: list[APIEndpoint] = field(default_factory=list)
    error: str = ""


class DocGeneratorConfig(BaseModel):
    """
    文档生成器配置
    
    Attributes:
        default_format: 默认格式
        doc_style: 文档风格
        include_private: 是否包含私有成员
        include_special: 是否包含特殊方法
        include_examples: 是否包含示例
        output_dir: 输出目录
    """
    default_format: DocFormat = DocFormat.MARKDOWN
    doc_style: DocStyle = DocStyle.GOOGLE
    include_private: bool = False
    include_special: bool = False
    include_examples: bool = True
    output_dir: str = "docs"


class DocGenerator:
    """
    文档自动生成器
    
    提供多种文档生成功能。
    
    Example:
        >>> generator = DocGenerator()
        >>> result = await generator.generate_api_docs(Path("./src"))
        >>> print(result.content)
    """

    def __init__(self, config: DocGeneratorConfig | None = None):
        """
        初始化文档生成器
        
        Args:
            config: 生成器配置
        """
        self.config = config or DocGeneratorConfig()
        logger.info("文档自动生成器初始化完成")

    async def generate_api_docs(
        self,
        source_path: Path,
        format: DocFormat | None = None,
    ) -> DocGenerationResult:
        """
        生成 API 文档
        
        Args:
            source_path: 源代码路径
            format: 文档格式
            
        Returns:
            生成结果
        """
        result = DocGenerationResult(format=format or self.config.default_format)

        try:
            # 收集所有 Python 文件
            python_files = list(source_path.rglob("*.py"))

            # 解析 API 端点
            endpoints = []
            for py_file in python_files:
                file_endpoints = self._extract_api_endpoints(py_file)
                endpoints.extend(file_endpoints)

            result.endpoints = endpoints

            # 生成文档
            if result.format == DocFormat.OPENAPI:
                result.content = self._generate_openapi_spec(endpoints)
            else:
                result.content = self._generate_markdown_docs(endpoints)

        except Exception as e:
            result.success = False
            result.error = str(e)
            logger.error(f"生成 API 文档失败: {e}")

        return result

    def _extract_api_endpoints(self, file_path: Path) -> list[APIEndpoint]:
        """从文件提取 API 端点"""
        endpoints = []

        try:
            with open(file_path, encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source)

            # 查找路由装饰器
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    endpoint = self._parse_route_decorator(node)
                    if endpoint:
                        endpoints.append(endpoint)

        except Exception as e:
            logger.debug(f"解析文件失败 {file_path}: {e}")

        return endpoints

    def _parse_route_decorator(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> APIEndpoint | None:
        """解析路由装饰器"""
        route_decorators = [
            "route", "get", "post", "put", "delete", "patch",
            "api_view", "endpoint",
        ]

        for decorator in node.decorator_list:
            # 处理 @app.route('/path') 或 @route('/path')
            if isinstance(decorator, ast.Call):
                func = decorator.func
                if isinstance(func, ast.Attribute):
                    decorator_name = func.attr.lower()
                elif isinstance(func, ast.Name):
                    decorator_name = func.id.lower()
                else:
                    continue

                if decorator_name in route_decorators:
                    # 提取路径
                    path = ""
                    if decorator.args:
                        if isinstance(decorator.args[0], ast.Constant):
                            path = decorator.args[0].value

                    # 提取方法
                    method = "GET"
                    if decorator_name in ("get", "post", "put", "delete", "patch"):
                        method = decorator_name.upper()

                    # 提取文档字符串
                    docstring = ast.get_docstring(node) or ""

                    return APIEndpoint(
                        path=path,
                        method=method,
                        summary=node.name.replace("_", " ").title(),
                        description=docstring,
                        tags=["API"],
                    )

        return None

    def _generate_openapi_spec(self, endpoints: list[APIEndpoint]) -> str:
        """生成 OpenAPI 规范"""
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "API Documentation",
                "version": "1.0.0",
                "description": "Auto-generated API documentation",
            },
            "paths": {},
        }

        for endpoint in endpoints:
            if endpoint.path not in spec["paths"]:
                spec["paths"][endpoint.path] = {}

            spec["paths"][endpoint.path][endpoint.method.lower()] = endpoint.to_openapi()

        return json.dumps(spec, indent=2, ensure_ascii=False)

    def _generate_markdown_docs(self, endpoints: list[APIEndpoint]) -> str:
        """生成 Markdown 文档"""
        lines = ["# API Documentation", ""]
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 按路径分组
        by_path: dict[str, list[APIEndpoint]] = {}
        for ep in endpoints:
            if ep.path not in by_path:
                by_path[ep.path] = []
            by_path[ep.path].append(ep)

        for path, eps in sorted(by_path.items()):
            lines.append(f"## `{path}`")
            lines.append("")

            for ep in eps:
                lines.append(f"### {ep.method}")
                lines.append("")
                if ep.summary:
                    lines.append(f"**摘要**: {ep.summary}")
                    lines.append("")
                if ep.description:
                    lines.append(ep.description)
                    lines.append("")
                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    async def generate_docstring(
        self,
        code: str,
        style: DocStyle | None = None,
    ) -> str:
        """
        生成代码注释
        
        Args:
            code: 代码字符串
            style: 文档风格
            
        Returns:
            添加了注释的代码
        """
        style = style or self.config.doc_style

        try:
            tree = ast.parse(code)

            # 为每个函数/类添加文档字符串
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not ast.get_docstring(node):
                        docstring = self._generate_function_docstring(node, style)
                        # 插入文档字符串
                        code = self._insert_docstring(code, node, docstring)

                elif isinstance(node, ast.ClassDef):
                    if not ast.get_docstring(node):
                        docstring = self._generate_class_docstring(node, style)
                        code = self._insert_docstring(code, node, docstring)

        except SyntaxError:
            pass

        return code

    def _generate_function_docstring(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        style: DocStyle,
    ) -> str:
        """生成函数文档字符串"""
        # 提取参数信息
        args = []
        for arg in node.args.args:
            arg_name = arg.arg
            arg_type = ""
            if arg.annotation:
                arg_type = ast.unparse(arg.annotation)
            args.append((arg_name, arg_type))

        # 提取返回类型
        returns = ""
        if node.returns:
            returns = ast.unparse(node.returns)

        if style == DocStyle.GOOGLE:
            return self._format_google_docstring(args, returns)
        elif style == DocStyle.NUMPY:
            return self._format_numpy_docstring(args, returns)
        elif style == DocStyle.SPHINX:
            return self._format_sphinx_docstring(args, returns)
        else:
            return self._format_google_docstring(args, returns)

    def _format_google_docstring(
        self,
        args: list[tuple[str, str]],
        returns: str,
    ) -> str:
        """格式化 Google 风格文档字符串"""
        lines = ['"""', "函数描述。", ""]

        if args:
            lines.append("Args:")
            for arg_name, arg_type in args:
                if arg_name == "self":
                    continue
                type_str = f" ({arg_type})" if arg_type else ""
                lines.append(f"    {arg_name}{type_str}: 参数描述。")
            lines.append("")

        if returns:
            lines.append("Returns:")
            lines.append(f"    {returns}: 返回值描述。")
            lines.append("")

        lines.append('"""')

        return "\n".join(lines)

    def _format_numpy_docstring(
        self,
        args: list[tuple[str, str]],
        returns: str,
    ) -> str:
        """格式化 NumPy 风格文档字符串"""
        lines = ['"""', "函数描述", ""]

        if args:
            lines.append("Parameters")
            lines.append("----------")
            for arg_name, arg_type in args:
                if arg_name == "self":
                    continue
                type_str = f" : {arg_type}" if arg_type else ""
                lines.append(f"{arg_name}{type_str}")
                lines.append("    参数描述。")
            lines.append("")

        if returns:
            lines.append("Returns")
            lines.append("-------")
            lines.append(f"{returns}")
            lines.append("    返回值描述。")
            lines.append("")

        lines.append('"""')

        return "\n".join(lines)

    def _format_sphinx_docstring(
        self,
        args: list[tuple[str, str]],
        returns: str,
    ) -> str:
        """格式化 Sphinx 风格文档字符串"""
        lines = ['"""函数描述。', ""]

        for arg_name, arg_type in args:
            if arg_name == "self":
                continue
            type_str = f" ({arg_type})" if arg_type else ""
            lines.append(f":param{type_str} {arg_name}: 参数描述。")

        if returns:
            lines.append(f":rtype: {returns}")
            lines.append(":return: 返回值描述。")

        lines.append('"""')

        return "\n".join(lines)

    def _generate_class_docstring(
        self,
        node: ast.ClassDef,
        style: DocStyle,
    ) -> str:
        """生成类文档字符串"""
        lines = ['"""', f"{node.name} 类。", ""]

        # 提取属性
        attributes = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name):
                    attr_name = item.target.id
                    attr_type = ""
                    if item.annotation:
                        attr_type = ast.unparse(item.annotation)
                    attributes.append((attr_name, attr_type))

        if attributes:
            lines.append("Attributes:")
            for attr_name, attr_type in attributes:
                type_str = f" ({attr_type})" if attr_type else ""
                lines.append(f"    {attr_name}{type_str}: 属性描述。")
            lines.append("")

        lines.append('"""')

        return "\n".join(lines)

    def _insert_docstring(
        self,
        code: str,
        node: ast.FunctionDef | ast.ClassDef,
        docstring: str,
    ) -> str:
        """插入文档字符串"""
        lines = code.split("\n")

        # 找到定义行
        def_line = node.lineno - 1

        # 找到函数体开始位置
        insert_line = def_line + 1
        indent = len(lines[def_line]) - len(lines[def_line].lstrip())
        indent_str = "    " if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "    "

        # 插入文档字符串
        docstring_lines = docstring.split("\n")
        indented_docstring = [indent_str + line for line in docstring_lines]

        for i, line in enumerate(indented_docstring):
            lines.insert(insert_line + i, line)

        return "\n".join(lines)

    async def generate_readme(
        self,
        project_path: Path,
    ) -> str:
        """
        生成 README
        
        Args:
            project_path: 项目路径
            
        Returns:
            README 内容
        """
        lines = []

        # 项目名称
        project_name = project_path.name
        lines.append(f"# {project_name}")
        lines.append("")

        # 描述
        lines.append("## 简介")
        lines.append("")
        lines.append(f"{project_name} 是一个 Python 项目。")
        lines.append("")

        # 安装
        lines.append("## 安装")
        lines.append("")
        lines.append("```bash")
        lines.append("pip install -r requirements.txt")
        lines.append("```")
        lines.append("")

        # 使用
        lines.append("## 使用")
        lines.append("")
        lines.append("```python")
        lines.append("import main")
        lines.append("")
        lines.append("# 使用示例")
        lines.append("```")
        lines.append("")

        # 项目结构
        lines.append("## 项目结构")
        lines.append("")
        lines.append("```")
        structure = self._get_project_structure(project_path)
        lines.append(structure)
        lines.append("```")
        lines.append("")

        # 依赖
        req_file = project_path / "requirements.txt"
        if req_file.exists():
            lines.append("## 依赖")
            lines.append("")
            lines.append("参见 `requirements.txt` 文件。")
            lines.append("")

        # 许可证
        lines.append("## 许可证")
        lines.append("")
        lines.append("MIT License")
        lines.append("")

        return "\n".join(lines)

    def _get_project_structure(self, project_path: Path, prefix: str = "") -> str:
        """获取项目结构"""
        lines = []

        items = sorted(project_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))

        for i, item in enumerate(items):
            # 跳过隐藏文件和常见排除目录
            if item.name.startswith(".") or item.name in [
                "__pycache__", "node_modules", "venv", ".venv",
                "dist", "build", "*.egg-info",
            ]:
                continue

            is_last = i == len(items) - 1
            current_prefix = "└── " if is_last else "├── "
            next_prefix = "    " if is_last else "│   "

            lines.append(f"{prefix}{current_prefix}{item.name}")

            if item.is_dir():
                sub_structure = self._get_project_structure(
                    item, prefix + next_prefix
                )
                if sub_structure:
                    lines.append(sub_structure)

        return "\n".join(lines)


# 创建默认文档生成器实例
doc_generator = DocGenerator()
