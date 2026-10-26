import asyncio

import pytest

pytest.importorskip("textual")


def test_tui_browse_and_favorite(library):
    from limpaper.tui.app import LimpaperTUI

    async def run():
        app = LimpaperTUI()
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause()
            assert len(app.shown) == 5
            await pilot.press("f")
            await pilot.pause()
            assert len(app.lp.state.favorites()) == 1
            await pilot.press("slash", *"rain")
            await pilot.pause()
            assert [w.name for w in app.shown] == ["city rain"]

    asyncio.run(run())
