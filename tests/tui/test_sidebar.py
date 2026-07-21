"""Standalone tests for sidebar rendering and delete behavior."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App
from textual.containers import Horizontal
from textual import on
from textual.widgets import Static

from foxcode.tui.widgets.sidebar import Sidebar, SessionRow


class FakeREPL(App):
    CSS = """
    Screen { background: #0d1117; color: #e6edf3; }
    Horizontal { height: 1fr; }
    #left  { width: 30; }
    #right { width: 1fr; }
    """

    def __init__(self):
        super().__init__()
        self._menu_calls: list[tuple[str, int, int]] = []

    def compose(self):
        with Horizontal():
            self.sidebar = Sidebar(id="left")
            yield self.sidebar
            self.log_area = Static("", id="right")
            yield self.log_area

    @on(SessionRow.MenuClicked)
    def _on_menu(self, event: SessionRow.MenuClicked):
        self._menu_calls.append((event.sid, event.x, event.y))
        self.log_area.update(f"menu: {self._menu_calls}")

    def mount_sessions(self, sessions: list[dict], current_id: str):
        self.sidebar.refresh_sessions(sessions, current_id)


async def test_list_item_height():
    app = FakeREPL()
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        app.mount_sessions(
            [
                {
                    "session_id": "s1",
                    "name": "名",
                    "created_at": "2025-01-15 10:30",
                    "message_count": 0,
                },
            ],
            current_id="s1",
        )
        await pilot.pause(0.2)

        items = list(app.sidebar.sessions.query(SessionRow))
        print(f"Item count: {len(items)}")
        item = items[0]
        print(f"Item size: {item.size}")
        print(f"Item classes: {item.classes}")
        print(f"Item sid: {item.sid}")

        # Write visual screenshot for human inspection
        svg = app.export_screenshot(title="debug-height")
        Path("sidebar_height_debug.svg").write_text(svg, encoding="utf-8")
        print("Screenshot written to sidebar_height_debug.svg")

        if item.size.height < 2:
            print(f"FAIL: height {item.size.height} < 2")
            return False
        print("PASS: height >= 2")
        return True


async def test_delete():
    app = FakeREPL()
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        app.mount_sessions(
            [
                {"session_id": "s1", "name": "A", "created_at": "", "message_count": 1},
                {"session_id": "s2", "name": "B", "created_at": "", "message_count": 2},
            ],
            current_id="s1",
        )
        await pilot.pause(0.2)
        items1 = list(app.sidebar.sessions.query(SessionRow))
        print(f"Before: {len(items1)} items")

        app.mount_sessions(
            [
                {"session_id": "s1", "name": "A", "created_at": "", "message_count": 1},
            ],
            current_id="s1",
        )
        await pilot.pause(0.2)
        items2 = list(app.sidebar.sessions.query(SessionRow))
        sids = [it.sid for it in items2]
        print(f"After: {len(items2)} items, sids={sids}")

        if "s2" in sids:
            print("FAIL: s2 still present after delete refresh")
            return False
        if len(items2) != 1:
            print(f"FAIL: expected 1 item, got {len(items2)}")
            return False
        print("PASS: delete refresh works")
        return True


async def main():
    ok1 = await test_list_item_height()
    ok2 = await test_delete()
    if ok1 and ok2:
        print("\nAll tests PASSED")
    else:
        print("\nSome tests FAILED")


if __name__ == "__main__":
    asyncio.run(main())
