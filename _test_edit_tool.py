"""Test EditFileTool with comment protection."""

import asyncio
import os
from pathlib import Path

from foxcode.core.comment_protect_manager import get_manager
from foxcode.tools.file_tools import EditFileTool


async def main():
    test_file = os.path.join(os.getcwd(), "_test_edit_protection.py")

    original = (
        "# Original header\n"
        "import os\n"
        "\n"
        "def old_func():\n"
        '    """Old docstring."""\n'
        "    # TODO: refactor\n"
        "    return 42  # magic number\n"
    )
    Path(test_file).write_text(original, encoding="utf-8")

    m = get_manager()
    m.enable()
    m.reset_stats()

    # Read back actual content
    actual = Path(test_file).read_text(encoding="utf-8")
    old_text = actual[actual.index("def old_func():") :]
    print("OLD_TEXT repr:")
    print(repr(old_text))

    # AI edits file via EditFileTool
    tool = EditFileTool()
    result = await tool.execute(
        test_file,
        old_text=old_text,
        new_text="def new_func():\n    return 42\n",
    )
    print("=== EditFileTool result ===")
    print(f"  success={result.success}")
    if result.error:
        print(f"  error={result.error!r}")

    final = Path(test_file).read_text(encoding="utf-8")
    print("=== FINAL FILE ===")
    print(final)
    print("=== STATS ===")
    print(m.get_stats().summary())


if __name__ == "__main__":
    asyncio.run(main())
