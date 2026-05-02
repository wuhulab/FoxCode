"""
FoxCode 多模态处理器 - 图像分析、架构图生成和数据可视化

这个文件提供多模态处理功能:
1. 图像分析：通过多模态 AI 模型分析图像内容
2. 架构图生成：生成 Mermaid / PlantUML 格式的架构图
3. 数据可视化：生成图表和可视化
4. UI 转代码：将设计图转换为代码

图像类型:
- SCREENSHOT: 屏幕截图
- DESIGN: 设计图
- DIAGRAM: 图表
- CODE: 代码截图
- ERROR: 错误截图
- UI: UI 界面

使用方式:
    from foxcode.core.multimodal_processor import MultimodalProcessor

    processor = MultimodalProcessor()
    result = await processor.analyze_image(image_path)
    diagram = processor.generate_architecture_diagram(structure)
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ImageType(str, Enum):
    """图像类型"""
    SCREENSHOT = "screenshot"     # 截图
    DESIGN = "design"             # 设计图
    DIAGRAM = "diagram"           # 图表
    CODE = "code"                 # 代码截图
    ERROR = "error"               # 错误截图
    UI = "ui"                     # UI 界面
    UNKNOWN = "unknown"           # 未知


class DiagramType(str, Enum):
    """图表类型"""
    FLOWCHART = "flowchart"       # 流程图
    SEQUENCE = "sequence"         # 时序图
    CLASS = "class"               # 类图
    STATE = "state"               # 状态图
    ER = "er"                     # ER 图
    GANTT = "gantt"               # 甘特图
    PIE = "pie"                   # 饼图
    MINDMAP = "mindmap"           # 思维导图
    ARCHITECTURE = "architecture"  # 架构图


class ChartType(str, Enum):
    """图表类型"""
    LINE = "line"                 # 折线图
    BAR = "bar"                   # 柱状图
    PIE = "pie"                   # 饼图
    SCATTER = "scatter"           # 散点图
    AREA = "area"                 # 面积图
    HEATMAP = "heatmap"           # 热力图
    TREEMAP = "treemap"           # 树图


@dataclass
class ImageAnalysis:
    """
    图像分析结果
    
    Attributes:
        image_type: 图像类型
        description: 描述
        elements: 识别的元素
        text_content: 文本内容
        ui_components: UI 组件
        colors: 颜色列表
        layout: 布局信息
        suggestions: 代码建议
    """
    image_type: ImageType = ImageType.UNKNOWN
    description: str = ""
    elements: list[dict[str, Any]] = field(default_factory=list)
    text_content: str = ""
    ui_components: list[dict[str, Any]] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    layout: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_type": self.image_type.value,
            "description": self.description,
            "elements": self.elements,
            "text_content": self.text_content,
            "ui_components": self.ui_components,
            "colors": self.colors,
            "layout": self.layout,
            "suggestions": self.suggestions,
        }


@dataclass
class DiagramResult:
    """
    图表生成结果
    
    Attributes:
        diagram_type: 图表类型
        format: 格式 (mermaid, plantuml)
        code: 生成的代码
        svg: SVG 内容（可选）
        description: 描述
    """
    diagram_type: DiagramType = DiagramType.FLOWCHART
    format: str = "mermaid"
    code: str = ""
    svg: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagram_type": self.diagram_type.value,
            "format": self.format,
            "code": self.code,
            "svg": self.svg,
            "description": self.description,
        }


@dataclass
class ChartResult:
    """
    图表生成结果
    
    Attributes:
        chart_type: 图表类型
        library: 图表库
        code: 生成的代码
        data: 数据
        options: 配置选项
    """
    chart_type: ChartType = ChartType.BAR
    library: str = "chart.js"
    code: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chart_type": self.chart_type.value,
            "library": self.library,
            "code": self.code,
            "data": self.data,
            "options": self.options,
        }


@dataclass
class UICodeSuggestion:
    """
    UI 代码建议
    
    Attributes:
        framework: 框架
        code: 生成的代码
        components: 组件列表
        styles: 样式代码
        explanation: 解释
    """
    framework: str = "react"
    code: str = ""
    components: list[str] = field(default_factory=list)
    styles: str = ""
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework": self.framework,
            "code": self.code,
            "components": self.components,
            "styles": self.styles,
            "explanation": self.explanation,
        }


class MultimodalConfig(BaseModel):
    """
    多模态配置
    
    Attributes:
        enable_image_analysis: 是否启用图像分析
        default_diagram_format: 默认图表格式
        default_chart_library: 默认图表库
        default_ui_framework: 默认 UI 框架
        max_image_size: 最大图像大小
    """
    enable_image_analysis: bool = True
    default_diagram_format: str = "mermaid"
    default_chart_library: str = "chart.js"
    default_ui_framework: str = "react"
    max_image_size: int = Field(default=10 * 1024 * 1024)  # 10MB


class MultimodalProcessor:
    """
    多模态处理器
    
    提供图像分析、架构图生成和数据可视化功能。
    
    Example:
        >>> processor = MultimodalProcessor()
        >>> analysis = await processor.analyze_image(Path("screenshot.png"))
        >>> diagram = processor.generate_architecture_diagram(structure)
    """

    def __init__(self, config: MultimodalConfig | None = None):
        """
        初始化处理器
        
        Args:
            config: 多模态配置
        """
        self.config = config or MultimodalConfig()
        logger.info("多模态处理器初始化完成")

    async def analyze_image(
        self,
        image_path: Path | None = None,
        image_data: bytes | None = None,
        image_base64: str | None = None,
    ) -> ImageAnalysis:
        """
        分析图像
        
        Args:
            image_path: 图像路径
            image_data: 图像二进制数据
            image_base64: Base64 编码的图像
            
        Returns:
            图像分析结果
        """
        analysis = ImageAnalysis()

        try:
            # 获取图像数据
            if image_path and image_path.exists():
                with open(image_path, "rb") as f:
                    image_data = f.read()

            if image_data:
                image_base64 = base64.b64encode(image_data).decode("utf-8")

            if not image_base64:
                analysis.description = "无法获取图像数据"
                return analysis

            # 尝试使用多模态模型分析
            try:
                import openai

                client = openai.OpenAI()
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "分析这张图片，识别其中的 UI 元素、布局、颜色和文本内容。如果是代码截图，请识别代码内容。如果是设计图，请描述设计风格。",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_base64}"
                                    },
                                },
                            ],
                        }
                    ],
                    max_tokens=1000,
                )

                analysis.description = response.choices[0].message.content or ""
                analysis.image_type = self._classify_image_type(analysis.description)

            except ImportError:
                # 没有安装 openai，使用简单分析
                analysis.description = "多模态模型不可用，无法分析图像"
                analysis.image_type = ImageType.UNKNOWN
            except Exception as e:
                logger.error(f"图像分析失败: {e}")
                analysis.description = f"分析失败: {str(e)}"

        except Exception as e:
            logger.error(f"图像分析失败: {e}")
            analysis.description = str(e)

        return analysis

    def _classify_image_type(self, description: str) -> ImageType:
        """根据描述分类图像类型"""
        desc_lower = description.lower()

        if "code" in desc_lower or "代码" in desc_lower:
            return ImageType.CODE
        elif "error" in desc_lower or "错误" in desc_lower:
            return ImageType.ERROR
        elif "design" in desc_lower or "设计" in desc_lower:
            return ImageType.DESIGN
        elif "ui" in desc_lower or "界面" in desc_lower:
            return ImageType.UI
        elif "diagram" in desc_lower or "图表" in desc_lower:
            return ImageType.DIAGRAM
        elif "screenshot" in desc_lower or "截图" in desc_lower:
            return ImageType.SCREENSHOT
        else:
            return ImageType.UNKNOWN

    def generate_architecture_diagram(
        self,
        structure: dict[str, Any],
        diagram_type: DiagramType = DiagramType.ARCHITECTURE,
        format: str = "mermaid",
    ) -> DiagramResult:
        """
        生成架构图
        
        Args:
            structure: 项目结构
            diagram_type: 图表类型
            format: 格式 (mermaid, plantuml)
            
        Returns:
            图表生成结果
        """
        result = DiagramResult(
            diagram_type=diagram_type,
            format=format,
        )

        if format == "mermaid":
            result.code = self._generate_mermaid_diagram(structure, diagram_type)
        elif format == "plantuml":
            result.code = self._generate_plantuml_diagram(structure, diagram_type)
        else:
            result.code = self._generate_mermaid_diagram(structure, diagram_type)

        result.description = f"生成的 {diagram_type.value} 图"
        return result

    def _generate_mermaid_diagram(
        self,
        structure: dict[str, Any],
        diagram_type: DiagramType,
    ) -> str:
        """生成 Mermaid 图表代码"""
        lines = []

        if diagram_type == DiagramType.FLOWCHART:
            lines.append("flowchart TD")
            self._add_flowchart_nodes(lines, structure, "")

        elif diagram_type == DiagramType.SEQUENCE:
            lines.append("sequenceDiagram")
            self._add_sequence_participants(lines, structure)
            self._add_sequence_messages(lines, structure)

        elif diagram_type == DiagramType.CLASS:
            lines.append("classDiagram")
            self._add_class_definitions(lines, structure)

        elif diagram_type == DiagramType.ARCHITECTURE:
            lines.append("flowchart TB")
            self._add_architecture_nodes(lines, structure)

        else:
            lines.append("flowchart TD")
            lines.append("    A[开始] --> B[结束]")

        return "\n".join(lines)

    def _add_flowchart_nodes(
        self,
        lines: list[str],
        structure: dict[str, Any],
        prefix: str,
    ) -> None:
        """添加流程图节点"""
        nodes = structure.get("nodes", [])
        edges = structure.get("edges", [])

        for node in nodes:
            node_id = node.get("id", "")
            node_label = node.get("label", node_id)
            node_type = node.get("type", "rect")

            if node_type == "diamond":
                lines.append(f"    {node_id}{{{node_label}}}")
            elif node_type == "circle":
                lines.append(f"    {node_id}(({node_label}))")
            else:
                lines.append(f"    {node_id}[{node_label}]")

        for edge in edges:
            from_id = edge.get("from", "")
            to_id = edge.get("to", "")
            label = edge.get("label", "")

            if label:
                lines.append(f"    {from_id} -->|{label}| {to_id}")
            else:
                lines.append(f"    {from_id} --> {to_id}")

    def _add_sequence_participants(
        self,
        lines: list[str],
        structure: dict[str, Any],
    ) -> None:
        """添加时序图参与者"""
        participants = structure.get("participants", [])
        for p in participants:
            name = p.get("name", "")
            alias = p.get("alias", name)
            lines.append(f"    participant {alias} as {name}")

    def _add_sequence_messages(
        self,
        lines: list[str],
        structure: dict[str, Any],
    ) -> None:
        """添加时序图消息"""
        messages = structure.get("messages", [])
        for msg in messages:
            from_p = msg.get("from", "")
            to_p = msg.get("to", "")
            content = msg.get("content", "")
            msg_type = msg.get("type", "sync")

            if msg_type == "async":
                lines.append(f"    {from_p}--)>>{to_p}: {content}")
            elif msg_type == "return":
                lines.append(f"    {to_p}-->>{from_p}: {content}")
            else:
                lines.append(f"    {from_p}->>{to_p}: {content}")

    def _add_class_definitions(
        self,
        lines: list[str],
        structure: dict[str, Any],
    ) -> None:
        """添加类定义"""
        classes = structure.get("classes", [])
        for cls in classes:
            name = cls.get("name", "")
            attributes = cls.get("attributes", [])
            methods = cls.get("methods", [])

            lines.append(f"    class {name} {{")
            for attr in attributes:
                lines.append(f"        {attr}")
            for method in methods:
                lines.append(f"        {method}")
            lines.append("    }")

        # 添加继承关系
        inheritance = structure.get("inheritance", [])
        for rel in inheritance:
            parent = rel.get("parent", "")
            child = rel.get("child", "")
            lines.append(f"    {parent} <|-- {child}")

    def _add_architecture_nodes(
        self,
        lines: list[str],
        structure: dict[str, Any],
    ) -> None:
        """添加架构图节点"""
        components = structure.get("components", [])
        connections = structure.get("connections", [])

        for comp in components:
            comp_id = comp.get("id", "")
            comp_name = comp.get("name", "")
            comp_type = comp.get("type", "service")

            # 使用子图表示不同层级
            if comp_type == "frontend":
                lines.append("    subgraph frontend [前端]")
                lines.append(f"        {comp_id}[{comp_name}]")
                lines.append("    end")
            elif comp_type == "backend":
                lines.append("    subgraph backend [后端]")
                lines.append(f"        {comp_id}[{comp_name}]")
                lines.append("    end")
            elif comp_type == "database":
                lines.append(f"    {comp_id}[({comp_name})]")
            else:
                lines.append(f"    {comp_id}[{comp_name}]")

        for conn in connections:
            from_id = conn.get("from", "")
            to_id = conn.get("to", "")
            label = conn.get("label", "")

            if label:
                lines.append(f"    {from_id} -->|{label}| {to_id}")
            else:
                lines.append(f"    {from_id} --> {to_id}")

    def _generate_plantuml_diagram(
        self,
        structure: dict[str, Any],
        diagram_type: DiagramType,
    ) -> str:
        """生成 PlantUML 图表代码"""
        lines = ["@startuml"]

        if diagram_type == DiagramType.SEQUENCE:
            participants = structure.get("participants", [])
            for p in participants:
                name = p.get("name", "")
                lines.append(f"participant {name}")

            messages = structure.get("messages", [])
            for msg in messages:
                from_p = msg.get("from", "")
                to_p = msg.get("to", "")
                content = msg.get("content", "")
                lines.append(f"{from_p} -> {to_p}: {content}")

        elif diagram_type == DiagramType.CLASS:
            classes = structure.get("classes", [])
            for cls in classes:
                name = cls.get("name", "")
                lines.append(f"class {name} {{")
                for attr in cls.get("attributes", []):
                    lines.append(f"  {attr}")
                for method in cls.get("methods", []):
                    lines.append(f"  {method}")
                lines.append("}")

        else:
            lines.append("node A")
            lines.append("node B")
            lines.append("A --> B")

        lines.append("@enduml")
        return "\n".join(lines)

    def generate_chart(
        self,
        data: dict[str, Any],
        chart_type: ChartType = ChartType.BAR,
        library: str = "chart.js",
        options: dict[str, Any] | None = None,
    ) -> ChartResult:
        """
        生成数据可视化图表
        
        Args:
            data: 图表数据
            chart_type: 图表类型
            library: 图表库
            options: 配置选项
            
        Returns:
            图表生成结果
        """
        result = ChartResult(
            chart_type=chart_type,
            library=library,
            data=data,
            options=options or {},
        )

        if library == "chart.js":
            result.code = self._generate_chartjs_code(data, chart_type, options)
        elif library == "echarts":
            result.code = self._generate_echarts_code(data, chart_type, options)
        elif library == "matplotlib":
            result.code = self._generate_matplotlib_code(data, chart_type, options)
        else:
            result.code = self._generate_chartjs_code(data, chart_type, options)

        return result

    def _generate_chartjs_code(
        self,
        data: dict[str, Any],
        chart_type: ChartType,
        options: dict[str, Any] | None,
    ) -> str:
        """生成 Chart.js 代码"""
        labels = data.get("labels", [])
        datasets = data.get("datasets", [])

        chart_type_map = {
            ChartType.LINE: "line",
            ChartType.BAR: "bar",
            ChartType.PIE: "pie",
            ChartType.SCATTER: "scatter",
            ChartType.AREA: "line",
        }

        js_chart_type = chart_type_map.get(chart_type, "bar")

        code = f"""const ctx = document.getElementById('myChart').getContext('2d');
const chart = new Chart(ctx, {{
    type: '{js_chart_type}',
    data: {{
        labels: {json.dumps(labels)},
        datasets: {json.dumps(datasets, indent=8)}
    }},
    options: {json.dumps(options or {}, indent=4)}
}});
"""
        return code

    def _generate_echarts_code(
        self,
        data: dict[str, Any],
        chart_type: ChartType,
        options: dict[str, Any] | None,
    ) -> str:
        """生成 ECharts 代码"""
        code = f"""const chart = echarts.init(document.getElementById('main'));
const option = {{
    xAxis: {{
        type: 'category',
        data: {json.dumps(data.get('labels', []))}
    }},
    yAxis: {{
        type: 'value'
    }},
    series: [{{
        data: {json.dumps(data.get('values', []))},
        type: '{chart_type.value}'
    }}]
}};
chart.setOption(option);
"""
        return code

    def _generate_matplotlib_code(
        self,
        data: dict[str, Any],
        chart_type: ChartType,
        options: dict[str, Any] | None,
    ) -> str:
        """生成 Matplotlib 代码"""
        code = f"""import matplotlib.pyplot as plt

labels = {json.dumps(data.get('labels', []))}
values = {json.dumps(data.get('values', []))}

fig, ax = plt.subplots()
ax.{chart_type.value}(labels, values)
ax.set_title('{options.get("title", "")}')
ax.set_xlabel('{options.get("xlabel", "")}')
ax.set_ylabel('{options.get("ylabel", "")}')

plt.savefig('chart.png')
plt.show()
"""
        return code

    def generate_ui_code(
        self,
        analysis: ImageAnalysis,
        framework: str = "react",
    ) -> UICodeSuggestion:
        """
        从设计图生成 UI 代码
        
        Args:
            analysis: 图像分析结果
            framework: 目标框架
            
        Returns:
            UI 代码建议
        """
        suggestion = UICodeSuggestion(framework=framework)

        if framework == "react":
            suggestion.code = self._generate_react_code(analysis)
            suggestion.components = self._extract_react_components(analysis)
        elif framework == "vue":
            suggestion.code = self._generate_vue_code(analysis)
            suggestion.components = self._extract_vue_components(analysis)
        elif framework == "html":
            suggestion.code = self._generate_html_code(analysis)
            suggestion.components = []

        suggestion.styles = self._generate_css_code(analysis)
        suggestion.explanation = f"基于图像分析生成的 {framework} 代码"

        return suggestion

    def _generate_react_code(self, analysis: ImageAnalysis) -> str:
        """生成 React 代码"""
        components = analysis.ui_components

        code = """import React from 'react';
import './styles.css';

const Component = () => {
    return (
        <div className="container">
"""

        for comp in components[:5]:  # 限制组件数量
            comp_type = comp.get("type", "div")
            comp_class = comp.get("class", "")
            comp_content = comp.get("content", "")

            code += f"""            <{comp_type} className="{comp_class}">
                {comp_content}
            </{comp_type}>
"""

        code += """        </div>
    );
};

export default Component;
"""
        return code

    def _generate_vue_code(self, analysis: ImageAnalysis) -> str:
        """生成 Vue 代码"""
        components = analysis.ui_components

        code = """<template>
    <div class="container">
"""

        for comp in components[:5]:
            comp_type = comp.get("type", "div")
            comp_class = comp.get("class", "")
            comp_content = comp.get("content", "")

            code += f"""        <{comp_type} class="{comp_class}">
            {comp_content}
        </{comp_type}>
"""

        code += """    </div>
</template>

<script>
export default {
    name: 'Component'
}
</script>
"""
        return code

    def _generate_html_code(self, analysis: ImageAnalysis) -> str:
        """生成 HTML 代码"""
        components = analysis.ui_components

        code = """<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
"""

        for comp in components[:5]:
            comp_type = comp.get("type", "div")
            comp_class = comp.get("class", "")
            comp_content = comp.get("content", "")

            code += f"""        <{comp_type} class="{comp_class}">
            {comp_content}
        </{comp_type}>
"""

        code += """    </div>
</body>
</html>
"""
        return code

    def _generate_css_code(self, analysis: ImageAnalysis) -> str:
        """生成 CSS 代码"""
        colors = analysis.colors[:5]
        layout = analysis.layout

        css = """.container {
    display: flex;
    flex-direction: column;
    padding: 20px;
}

"""

        for i, color in enumerate(colors):
            css += f""".color-{i+1} {{
    background-color: {color};
}}

"""

        return css

    def _extract_react_components(self, analysis: ImageAnalysis) -> list[str]:
        """提取 React 组件列表"""
        return [comp.get("type", "div") for comp in analysis.ui_components]

    def _extract_vue_components(self, analysis: ImageAnalysis) -> list[str]:
        """提取 Vue 组件列表"""
        return [comp.get("type", "div") for comp in analysis.ui_components]


# 创建默认多模态处理器实例
multimodal_processor = MultimodalProcessor()
