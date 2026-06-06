"""Test EditFileTool with comment protection (CRLF aware)."""

import asyncio
import os
from pathlib import Path

from foxcode.core.comment_protect_manager import get_manager
from foxcode.tools.file_tools import EditFileTool


async def main():
    test_file = os.path.join(os.getcwd(), "_test_edit_protection.py")
    Path(test_file).write_bytes(
        (
            b"# Original header\r\n"
            b"import os\r\n"
            b"\r\n"
            b"def old_func():\r\n"
            b'    """Old docstring."""\r\n'
            b"    # TODO: refactor\r\n"
            b"    return 42  # magic number\r\n"
        ),
    )

    m = get_manager()
    m.enable()
    m.reset_stats()

    old_text = (
        "def old_func():\r\n"
        '    """Old docstring."""\r\n'
        "    # TODO: refactor\r\n"
        "    return 42  # magic number\r\n"
    )

    tool = EditFileTool()
    result = await tool.execute(
        test_file,
        old_text=old_text,
        new_text="def new_func():\r\n    return 42\r\n",
    )
    print(f"success={result.success}")
    if result.error:
        print(f"error={result.error!r}")
    else:
        print(f"output={result.output!r}")

    final = Path(test_file).read_text(encoding="utf-8")
    print("=== FINAL FILE ===")
    print(final)
    print("=== STATS ===")
    print(m.get_stats().summary())


if __name__ == "__main__":
    asyncio.run(main())
