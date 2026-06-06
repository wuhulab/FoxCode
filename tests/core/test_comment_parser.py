"""
test_comment_parser.py — 注释解析器测试。

覆盖：
- 多语言注释识别
- 行注释、块注释、文档字符串
- 字符串字面量中的伪注释
- 锚点计算和独立成行判断
"""

from foxcode.core.comment_parser import (
    CommentParser,
    CommentType,
    get_parser_for_file,
)


class TestLineComments:
    """行注释测试"""

    def test_python_line_comment(self):
        parser = CommentParser("test.py")
        comments = parser.parse("# hello\nimport os\n")
        assert len(comments) == 1
        assert comments[0].text == "# hello"
        assert comments[0].comment_type == CommentType.LINE
        assert comments[0].start_line == 0
        assert comments[0].standalone is True

    def test_c_style_line_comment(self):
        parser = CommentParser("test.js")
        comments = parser.parse("// hello\nconst x = 1;\n")
        assert len(comments) == 1
        assert comments[0].text == "// hello"
        assert comments[0].comment_type == CommentType.LINE

    def test_sql_line_comment(self):
        parser = CommentParser("test.sql")
        comments = parser.parse("-- hello\nSELECT * FROM t;\n")
        assert len(comments) == 1
        assert comments[0].text == "-- hello"
        assert comments[0].comment_type == CommentType.LINE

    def test_lua_line_comment(self):
        parser = CommentParser("test.lua")
        comments = parser.parse("-- hello\nlocal x = 1\n")
        assert len(comments) == 1
        assert comments[0].text == "-- hello"
        assert comments[0].comment_type == CommentType.LINE

    def test_inline_comment(self):
        parser = CommentParser("test.py")
        comments = parser.parse("x = 1  # inline\n")
        assert len(comments) == 1
        assert comments[0].text == "# inline"
        assert comments[0].standalone is False
        assert comments[0].anchor_text == "x = 1"

    def test_crlf_line_endings(self):
        parser = CommentParser("test.py")
        comments = parser.parse("# hello\r\nimport os\r\n")
        assert len(comments) == 1
        assert comments[0].text == "# hello"
        assert "\r" not in comments[0].text


class TestBlockComments:
    """块注释测试"""

    def test_single_line_block(self):
        parser = CommentParser("test.c")
        comments = parser.parse("/* hello */\nint x;\n")
        assert len(comments) == 1
        assert comments[0].text == "/* hello */"
        assert comments[0].comment_type == CommentType.BLOCK

    def test_multi_line_block(self):
        parser = CommentParser("test.c")
        code = "/*\n * hello\n * world\n */\nint x;\n"
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].start_line == 0
        assert comments[0].end_line == 3
        assert comments[0].comment_type == CommentType.BLOCK

    def test_ruby_begin_end(self):
        parser = CommentParser("test.rb")
        code = "=begin\nhello\n=end\nputs 'x'\n"
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].comment_type == CommentType.BLOCK

    def test_lua_long_block(self):
        parser = CommentParser("test.lua")
        code = "--[[\nhello\n]]\nlocal x = 1\n"
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].comment_type == CommentType.BLOCK


class TestDocstrings:
    """文档字符串测试"""

    def test_function_docstring(self):
        parser = CommentParser("test.py")
        code = 'def foo():\n    """Hello."""\n    return 1\n'
        comments = parser.parse(code)
        # 1 docstring
        assert len(comments) == 1
        assert comments[0].comment_type == CommentType.DOCSTRING
        assert comments[0].text == '"""Hello."""'

    def test_multi_line_docstring(self):
        parser = CommentParser("test.py")
        code = 'def foo():\n    """\n    Hello.\n    """\n    return 1\n'
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].comment_type == CommentType.DOCSTRING
        assert comments[0].start_line == 1
        assert comments[0].end_line == 3

    def test_triple_quoted_string_not_docstring(self):
        """三引号字符串中包含代码时不应识别为 docstring"""
        parser = CommentParser("test.py")
        code = 'def foo():\n    x = """hello""" + "world"\n    return x\n'
        comments = parser.parse(code)
        # 不应识别为 docstring（不是独立行）
        assert len(comments) == 0


class TestHTMLComments:
    """HTML 注释测试"""

    def test_html_comment(self):
        parser = CommentParser("test.html")
        comments = parser.parse("<!-- hello -->\n<div></div>\n")
        assert len(comments) == 1
        assert comments[0].text == "<!-- hello -->"
        assert comments[0].comment_type == CommentType.HTML

    def test_xml_comment(self):
        parser = CommentParser("test.xml")
        comments = parser.parse("<!-- header -->\n<root/>\n")
        assert len(comments) == 1
        assert comments[0].comment_type == CommentType.HTML


class TestStringLiterals:
    """字符串字面量测试 - 确保不误判"""

    def test_hash_in_string(self):
        """字符串中的 # 不应被识别为注释"""
        parser = CommentParser("test.py")
        comments = parser.parse('s = "hello # world"\n')
        assert len(comments) == 0

    def test_double_slash_in_string(self):
        """字符串中的 // 不应被识别为注释"""
        parser = CommentParser("test.js")
        comments = parser.parse('var s = "hello // world";\n')
        assert len(comments) == 0

    def test_dash_dash_in_string(self):
        """字符串中的 -- 不应被识别为注释"""
        parser = CommentParser("test.sql")
        comments = parser.parse("SELECT '-- not a comment' FROM t;\n")
        assert len(comments) == 0

    def test_url_in_string(self):
        """URL 不应被识别为注释"""
        parser = CommentParser("test.py")
        comments = parser.parse('url = "https://example.com/path"\n')
        assert len(comments) == 0

    def test_escaped_quote_in_string(self):
        """转义引号应正确处理"""
        parser = CommentParser("test.py")
        comments = parser.parse('s = "hello \\" # not comment"\n')
        assert len(comments) == 0


class TestAnchors:
    """锚点计算测试"""

    def test_standalone_anchor_finds_next_line(self):
        parser = CommentParser("test.py")
        code = "# header\nimport os\n"
        comments = parser.parse(code)
        assert comments[0].standalone is True
        assert comments[0].anchor_line == 1
        assert comments[0].anchor_text == "import os"

    def test_inline_anchor_is_same_line(self):
        parser = CommentParser("test.py")
        code = "x = 1  # inline\n"
        comments = parser.parse(code)
        assert comments[0].standalone is False
        assert comments[0].anchor_line == 0
        assert comments[0].anchor_text == "x = 1"

    def test_anchor_strips_inline_comment(self):
        """锚点应剥离行内注释"""
        parser = CommentParser("test.py")
        code = "x = 1  # comment\ny = 2\n"
        comments = parser.parse(code)
        # x = 1 的锚点是它自己（行内注释）
        # 第二个注释（如果有）的锚点
        assert len(comments) == 1
        assert comments[0].anchor_text == "x = 1"
        assert "#" not in comments[0].anchor_text

    def test_anchor_falls_back_to_previous(self):
        """独立注释在文件末尾时，锚点向前查找"""
        parser = CommentParser("test.py")
        code = "import os\nx = 1\n# trailing\n"
        comments = parser.parse(code)
        # 末尾注释的锚点：往后找不到，往前找
        assert comments[0].standalone is True
        assert comments[0].anchor_line == 1
        assert comments[0].anchor_text == "x = 1"


class TestStripComments:
    """strip_comments 方法测试"""

    def test_strip_simple_comments(self):
        parser = CommentParser("test.py")
        code = "# header\nimport os\nx = 1  # inline\n"
        result = parser.strip_comments(code)
        # 行结构应保持
        assert result.count("\n") == code.count("\n")
        # 注释应被剥离
        assert "# header" not in result
        assert "import os" in result
        # 整行注释（# header）变成空行
        lines = result.splitlines()
        assert lines[0] == ""
        assert lines[1] == "import os"
        # 行内注释的代码部分应保留
        assert lines[2] == "x = 1"


class TestSupportedExtensions:
    """扩展名识别测试"""

    def test_python_supported(self):
        assert CommentParser.is_supported("test.py")

    def test_javascript_supported(self):
        assert CommentParser.is_supported("test.js")

    def test_html_supported(self):
        assert CommentParser.is_supported("test.html")

    def test_unsupported_extension(self):
        # 二进制文件不应被支持
        assert not CommentParser.is_supported("test.exe")
        assert not CommentParser.is_supported("test.bin")

    def test_get_parser_for_file(self):
        parser = get_parser_for_file("test.py")
        assert isinstance(parser, CommentParser)
        assert parser._syntax.get("docstring") is True


class TestReturnType:
    """返回类型测试"""

    def test_parse_returns_list(self):
        parser = CommentParser("test.py")
        result = parser.parse("# hi\n")
        assert isinstance(result, list)
