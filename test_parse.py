import sys
sys.path.insert(0, r'S:\shunxcode\src')
from foxcode.core.agent import FoxCodeAgent

def test_parse(label, text, expected_tool=None):
    a = object.__new__(FoxCodeAgent)
    result = a._parse_tool_call(text)
    tool, params, remaining = result
    ok = tool == expected_tool if expected_tool else tool is None
    status = 'OK' if ok else 'FAIL'
    print(f'[{status}] {label}: tool={tool}, params={params}')
    return result

# 合法调用
test_parse('standard function', '<function=shell_execute><parameter=command>del x.svg</parameter></function>', 'shell_execute')
test_parse('standard bracket inline', '[tool] list_directory S:\shunxcode', 'list_directory')
test_parse('bracket cross-line param', '[tool] shell_execute \ndel x.svg\n\nAfter empty', 'shell_execute')
test_parse('bracket cross-line param2', '[tool] grep \n\\.svg\n\nAfter', 'grep')

# 噪声调用（以前会失败/误解析）
test_parse('empty bracket then [say]', '[tool] shell_execute \n[say] Found 6 test SVG files', None)
test_parse('empty bracket then [say]2 with closing tag', '[tool] shell_execute \n[say] <tool_result>\n<tool_name>shell_execute</tool_name>\n</tool_result>', None)
test_parse('model self tool_result block', '<tool_result>\n<tool_name>grep</tool_name>\n</tool_result>\n[tool] list_directory S:\shunxcode', 'list_directory')
test_parse('tool_execute residue then [tool]', '<tool_execute>\n</tool_execute>\n[tool] read_file foo.py', 'read_file')
test_parse('bracket then markdown fence', '[tool] shell_execute \n```xml\n<parameter=command>del x.svg</parameter>\n```', 'shell_execute')
test_parse('inline contaminated by [say]', '[tool] shell_execute [say] Found...', None)

# 额外边界情况
test_parse('only [tool] shell_execute no param', '[tool] shell_execute', None)
test_parse('[tool] list_directory no param', '[tool] list_directory', 'list_directory')  # list_directory is safe, empty param OK

test_parse('contaminated by tool_execute', '[tool] shell_execute <tool_execute>foo</tool_execute>', None)

print('\nAll tests done.')
