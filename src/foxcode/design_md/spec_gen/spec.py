"""
spec_gen/spec.py — spec 模板内容（内嵌为字符串常量）。
"""

from __future__ import annotations

# 规范文档的 MDX 源内容，Python 版内嵌为字符串常量
# 替代 TypeScript 版的 MDX 编译器
SPEC_TEMPLATE = """
# DESIGN.md Format Specification

Version: {version}

## Overview

A DESIGN.md file bridges design systems and code.
"""
