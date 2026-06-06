import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from foxcode.tui.app import FoxCodeApp
from foxcode.core.config import Config, RunMode

agent = MagicMock()
agent.config = Config.create(run_mode=RunMode.DEFAULT)
agent.session = MagicMock()
agent.session.session_id = "test-session-12345678"
agent.session.conversation = []
agent.session.save = MagicMock()
agent.get_token_usage = MagicMock(return_value={"total_tokens": 1234})
agent.initialize = AsyncMock(return_value=None)


async def fake_chat(prompt):
    for chunk in ["Sure! ", "Here's a ", "```python\n", "print('hi')\n", "```\n", "Done."]:
        yield chunk


agent.chat = fake_chat


async def test():
    app = FoxCodeApp(agent, agent.config)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        # Save a screenshot of the initial state
        Path("tui_initial.svg").write_bytes(
            app.export_screenshot(title="FoxCode TUI - Initial").encode("utf-8")
        )
        print(f"Initial screenshot: {Path('tui_initial.svg').stat().st_size} bytes")

        # Type a prompt and send it
        prompt = app.query_one("#prompt")
        prompt.focus()
        await pilot.pause()
        await pilot.press(*"write hello world")
        await pilot.pause()
        # Press Enter to send
        await pilot.press("enter")
        # Let the worker stream
        for _ in range(20):
            await pilot.pause(0.1)
        # Save a screenshot after streaming
        Path("tui_streamed.svg").write_bytes(
            app.export_screenshot(title="FoxCode TUI - Streamed").encode("utf-8")
        )
        print(f"Streamed screenshot: {Path('tui_streamed.svg').stat().st_size} bytes")

        # Verify messages mounted
        all_msgs = app.query("Message")
        chat_children = list(app.query_one("#chat").children)
        print(f"Message widgets: {len(all_msgs)} | chat children: {len(chat_children)}")
        for c in chat_children:
            print(f"  - {type(c).__name__} classes={c.classes!r}")
        assert len(all_msgs) >= 2, f"expected at least user + assistant, got {len(all_msgs)}"
    print("TUI test PASSED")


asyncio.run(test())
