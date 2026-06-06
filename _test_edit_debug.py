"""Debug EditFileTool matching."""

import asyncio
import os
from pathlib import Path
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

    # Read with same method as EditFileTool
    import aiofiles
    from foxcode.utils.encoding import decode_bytes

    async with aiofiles.open(test_file, "rb") as f:
        raw_data = await f.read()
    content, detected_encoding = decode_bytes(raw_data)

    old_text = original[original.index("def old_func():") :]
    print(f"encoding={detected_encoding}")
    print(f"old_text in content? {old_text in content}")
    print(f"content repr={repr(content[:100])}")
    print(f"old_text repr={repr(old_text[:50])}")

    # Also test with WriteFileTool on same content
    tool = EditFileTool()
    result = await tool.execute(
        test_file, old_text=old_text, new_text="def new_func():\n    return 42\n"
    )
    print(f"result.success={result.success}")
    if result.error:
        print(f"error={result.error!r}")


if __name__ == "__main__":
    asyncio.run(main())
