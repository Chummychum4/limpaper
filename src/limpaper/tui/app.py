"""Terminal interface, built on Textual.

Left: categories (plus Favourites, Recent and All). Right: the wallpapers in
the selected view with a live filter. Everything is reachable from the
keyboard and listed in the footer; the mouse works too.
"""

from __future__ import annotations

import threading
import webbrowser
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    Static,
    Tab,
    Tabs,
)

from ..backends import BackendError
from ..core import Limpaper
from ..library import LibraryError, Wallpaper, pretty
from ..sources import SOURCES, THIRD_PARTY_WARNING, OnlineWallpaper, SourceError

LOGO = "┬  ┬┌┬┐┌─┐┌─┐┌─┐┌─┐┬─┐\n│  │││││├─┘├─┤├─┘├┤ ├┬┘\n┴─┘┴┴ ┴┴  ┴ ┴┴  └─┘┴└─"

FAVORITES = "\x00favorites"
RECENT = "\x00recent"
ALL = "\x00all"


# ── Dialogs ──────────────────────────────────────────────────────────────────
class Prompt(ModalScreen[Optional[str]]):
    """Ask for one line of text."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, placeholder: str = "", value: str = ""):
        super().__init__()
        self.title_text, self.placeholder, self.value = title, placeholder, value

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.title_text, classes="dialog-title")
            yield Input(value=self.value, placeholder=self.placeholder, id="prompt-input")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("OK", variant="primary", id="ok")

    @on(Input.Submitted)
    @on(Button.Pressed, "#ok")
    def _ok(self) -> None:
        self.dismiss(self.query_one(Input).value.strip() or None)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class Confirm(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "no", "No"), Binding("y", "yes", "Yes")]

    def __init__(self, question: str, yes: str = "Yes", warning: bool = False):
        super().__init__()
        self.question, self.yes, self.warning = question, yes, warning

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog warning" if self.warning else "dialog"):
            yield Static(self.question, classes="dialog-body")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Go back", id="no")
                yield Button(self.yes, variant="warning" if self.warning else "primary", id="yes")

    @on(Button.Pressed, "#yes")
    def action_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def action_no(self) -> None:
        self.dismiss(False)


class Choose(ModalScreen[Optional[str]]):
    """Pick one of a few strings."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, options: list[str]):
        super().__init__()
        self.title_text, self.options = title, options

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.title_text, classes="dialog-title")
            yield ListView(*(ListItem(Label(o), name=o) for o in self.options), id="choices")

    @on(ListView.Selected)
    def _picked(self, event: ListView.Selected) -> None:
        self.dismiss(event.item.name)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Online browser ───────────────────────────────────────────────────────────
class OnlineScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("d", "get(False)", "Download"),
        Binding("m", "more", "More results"),
        Binding("w", "open_page", "Open in browser"),
        Binding("slash", "focus_search", "Search"),
        Binding("c", "cancel_download", "Cancel download", show=False),
    ]

    def __init__(self, lp: Limpaper):
        super().__init__()
        self.lp = lp
        self.source = next(iter(SOURCES.values()))
        self.items: list[OnlineWallpaper] = []
        self.page = 1
        self.has_more = False
        self.query_text = ""
        self.cancel = threading.Event()
        self.downloading = False

    def compose(self) -> ComposeResult:
        yield Static("⚠  " + THIRD_PARTY_WARNING, id="online-warning")
        yield Tabs(*(Tab(f"{s.name} · {s.kind}", id=s.id) for s in SOURCES.values()), id="source-tabs")
        yield Input(placeholder="Search, or leave empty to browse the newest — press Enter", id="online-search")
        yield DataTable(id="online-table", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="online-status-bar"):
            yield Label("", id="online-status")
            yield ProgressBar(id="online-progress", show_eta=False)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("#", width=4, key="n")
        table.add_column("Title", key="title")
        table.add_column("Type", width=6, key="kind")
        table.add_column("Resolution", width=11, key="res")
        self.query_one(ProgressBar).display = False
        self.load(reset=True)

    def status(self, text: str) -> None:
        self.query_one("#online-status", Label).update(text)

    @on(Tabs.TabActivated)
    def _source_changed(self, event: Tabs.TabActivated) -> None:
        if event.tab and event.tab.id in SOURCES and SOURCES[event.tab.id] is not self.source:
            self.source = SOURCES[event.tab.id]
            self.load(reset=True)

    @on(Input.Submitted, "#online-search")
    def _search(self, event: Input.Submitted) -> None:
        self.query_text = event.value.strip()
        self.load(reset=True)
        self.query_one(DataTable).focus()

    def action_focus_search(self) -> None:
        self.query_one("#online-search", Input).focus()

    def action_back(self) -> None:
        self.cancel.set()
        self.dismiss()

    def action_more(self) -> None:
        if self.has_more:
            self.load(reset=False)
        else:
            self.status("No more results.")

    def load(self, reset: bool) -> None:
        if reset:
            self.page, self.items = 1, []
            self.query_one(DataTable).clear()
        else:
            self.page += 1
        what = f"“{self.query_text}”" if self.query_text else "newest"
        self.status(f"Loading {what} from {self.source.name}…")
        self._fetch(self.source, self.query_text, self.page)

    @work(thread=True, exclusive=True, group="fetch")
    def _fetch(self, source, query: str, page: int) -> None:
        safe = self.lp.settings.safe_search
        try:
            result = source.search(query, page, safe) if query else source.browse(page, safe)
        except SourceError as exc:
            self.app.call_from_thread(self.status, f"[red]{exc}[/]")
            return
        self.app.call_from_thread(self._show, source, result)

    def _show(self, source, result) -> None:
        if source is not self.source:
            return
        table = self.query_one(DataTable)
        for item in result.items:
            self.items.append(item)
            table.add_row(str(len(self.items)), item.title, item.kind, item.resolution or "—",
                          key=str(len(self.items) - 1))
        self.has_more = result.has_more
        more = "  ·  m: more" if result.has_more else ""
        self.status(f"{len(self.items)} wallpapers from {source.name}  ·  Enter: get & apply  ·  d: download only{more}")

    def _selected(self) -> OnlineWallpaper | None:
        table = self.query_one(DataTable)
        if not self.items or table.cursor_row is None or table.cursor_row >= len(self.items):
            return None
        return self.items[table.cursor_row]

    def action_open_page(self) -> None:
        item = self._selected()
        if item:
            webbrowser.open(item.page_url)

    def action_cancel_download(self) -> None:
        self.cancel.set()

    def action_get(self, apply: bool) -> None:
        if isinstance(self.focused, Input):
            return
        item = self._selected()
        if not item:
            return
        if self.downloading:
            self.status("A download is already running (c cancels it).")
            return
        self.downloading = True
        self.cancel = threading.Event()
        bar = self.query_one(ProgressBar)
        bar.update(total=None, progress=0)
        bar.display = True
        self.status(f"Downloading {item.title}…  (c cancels)")
        self._download(item, self.source, apply)

    @on(DataTable.RowSelected)
    def _row_selected(self) -> None:
        self.action_get(True)

    @work(thread=True, group="download")
    def _download(self, item, source, apply: bool) -> None:
        from ..download import DownloadError, download

        bar = self.query_one(ProgressBar)

        def progress(got: int, total: int) -> None:
            self.app.call_from_thread(bar.update, total=total or None, progress=got)

        try:
            path = download(item, source, self.lp.library, self.lp.settings.download_category,
                            progress, self.cancel)
            msg = f"[green]✓ Saved to {path}[/]"
            if apply:
                self.lp.apply(path)
                msg = f"[green]✓ Now playing {pretty(str(path))}[/]"
        except (DownloadError, SourceError, BackendError, OSError) as exc:
            msg = f"[red]{exc}[/]"
        self.app.call_from_thread(self._download_done, msg)

    def _download_done(self, msg: str) -> None:
        self.downloading = False
        self.query_one(ProgressBar).display = False
        self.status(msg)


# ── Main screen ──────────────────────────────────────────────────────────────
class LimpaperTUI(App):
    CSS_PATH = "app.tcss"
    TITLE = "limpaper"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("slash", "focus_filter", "Filter"),
        Binding("r", "random", "Random"),
        Binding("s", "stop", "Stop"),
        Binding("f", "favorite", "Fav"),
        Binding("o", "online", "Discover"),
        Binding("a", "add", "Add files"),
        Binding("n", "new_category", "New category"),
        Binding("m", "move", "Move", show=False),
        Binding("delete", "delete", "Delete", show=False),
        Binding("f5", "rescan", "Rescan", show=False),
        Binding("ctrl+r", "rescan", "Rescan", show=False),
        Binding("escape", "clear_filter", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.lp = Limpaper()
        self.view = ALL
        self.shown: list[Wallpaper] = []

    def check_action(self, action: str, parameters) -> bool | None:
        # Library keys only apply on the library screen, not over Discover
        if action != "quit" and isinstance(self.screen, OnlineScreen):
            return False
        return True

    def compose(self) -> ComposeResult:
        with Horizontal(id="top"):
            yield Static(LOGO, id="logo")
            with Vertical(id="now"):
                yield Label("", id="now-playing")
                yield Label("", id="now-path")
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Label("LIBRARY", classes="section")
                yield ListView(id="categories")
            with Vertical(id="main"):
                yield Input(placeholder="Filter wallpapers…  ( / )", id="filter")
                yield DataTable(id="walls", cursor_type="row", zebra_stripes=True)
                yield Label("", id="message")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#walls", DataTable)
        table.add_column("#", width=4, key="n")
        table.add_column("Name", key="name")
        table.add_column("", width=2, key="fav")
        table.add_column("Type", width=6, key="kind")
        table.add_column("Category", key="cat")
        self.refresh_all()
        table.focus()
        # Pick up folders and files added elsewhere (file manager, downloads)
        self._snapshot = self._library_snapshot()
        self.set_interval(5, self._poll)
        ok, why = self.lp.backend.available()
        if not ok:
            self.message(f"[yellow]{why}[/]")

    # ── Data ────────────────────────────────────────────────────────────────
    def _library_snapshot(self) -> tuple:
        lib = self.lp.library
        return tuple((c, lib.count(c)) for c in lib.categories())

    def _poll(self) -> None:
        if isinstance(self.screen, OnlineScreen) or len(self.screen_stack) > 1:
            return
        snap = self._library_snapshot()
        if snap != self._snapshot:
            self._snapshot = snap
            self.refresh_categories()
            self.refresh_walls()
        self.refresh_now()

    def refresh_all(self) -> None:
        self.refresh_now()
        self.refresh_categories()
        self.refresh_walls()

    def refresh_now(self) -> None:
        current = self.lp.current
        if current and self.lp.is_active():
            self.query_one("#now-playing", Label).update(Text.assemble(("▶ now playing  ", "dim"), (pretty(str(current)), "bold")))
            self.query_one("#now-path", Label).update(Text(str(current), style="dim"))
        else:
            self.query_one("#now-playing", Label).update(Text("■ no wallpaper running", style="dim"))
            self.query_one("#now-path", Label).update(Text(f"library: {self.lp.library.root}", style="dim"))

    def refresh_categories(self) -> None:
        lv = self.query_one("#categories", ListView)
        lib = self.lp.library
        cats = lib.categories()
        entries = [(ALL, "◆ All", sum(lib.count(c) for c in cats)),
                   (FAVORITES, "★ Favourites", len(self.lp.state.favorites())),
                   (RECENT, "◷ Recent", len(self.lp.state.history()))]
        entries += [(c, c, lib.count(c)) for c in cats]
        if self.view not in [e[0] for e in entries]:
            self.view = ALL
        lv.clear()
        index = 0
        for i, (key, label, count) in enumerate(entries):
            item = ListItem(Label(Text.assemble(label, (f"  {count}", "dim"))), name=key)
            if i == 3:
                item.add_class("first-category")
            lv.append(item)
            if key == self.view:
                index = i
        lv.index = index

    def _view_items(self) -> list[Wallpaper]:
        lib, state = self.lp.library, self.lp.state
        if self.view == FAVORITES:
            favs = state.favorites()
            return [w for w in lib.wallpapers() if str(w.path) in favs]
        if self.view == RECENT:
            by_path = {str(w.path): w for w in lib.wallpapers()}
            return [by_path[h] for h in state.history() if h in by_path]
        return lib.wallpapers(None if self.view == ALL else self.view)

    def refresh_walls(self) -> None:
        table = self.query_one("#walls", DataTable)
        needle = self.query_one("#filter", Input).value.strip().casefold()
        row = table.cursor_row
        items = self._view_items()
        if needle:
            items = [w for w in items if needle in w.name.casefold() or needle in w.category.casefold()]
        self.shown = items
        favs = self.lp.state.favorites()
        current = self.lp.current
        table.clear()
        for i, w in enumerate(items):
            name = Text(w.name, style="bold green" if w.path == current else "")
            cat = w.category + (f"/{w.subfolder}" if w.subfolder else "")
            table.add_row(str(i + 1), name, "★" if str(w.path) in favs else "",
                          w.kind, Text(cat, style="dim"), key=str(i))
        if items:
            table.move_cursor(row=min(row or 0, len(items) - 1))
        if not items:
            if not self.lp.library.exists():
                self.message(f"[yellow]Wallpaper folder {self.lp.library.root} does not exist yet — press n to create a category, or o to download some.[/]")
            elif self.view not in (FAVORITES, RECENT, ALL) or not needle:
                self.message("[dim]Nothing here yet. Press a to add files, or o to discover wallpapers online.[/]")

    def message(self, text: str) -> None:
        self.query_one("#message", Label).update(text)

    def selected(self) -> Wallpaper | None:
        table = self.query_one("#walls", DataTable)
        if not self.shown or table.cursor_row is None or table.cursor_row >= len(self.shown):
            return None
        return self.shown[table.cursor_row]

    # ── Events ──────────────────────────────────────────────────────────────
    @on(ListView.Highlighted, "#categories")
    def _category_changed(self, event: ListView.Highlighted) -> None:
        if event.item is not None and event.item.name != self.view:
            self.view = event.item.name
            self.refresh_walls()

    @on(ListView.Selected, "#categories")
    def _category_selected(self) -> None:
        self.query_one("#walls", DataTable).focus()

    @on(Input.Changed, "#filter")
    def _filter_changed(self) -> None:
        self.refresh_walls()

    @on(Input.Submitted, "#filter")
    def _filter_done(self) -> None:
        self.query_one("#walls", DataTable).focus()

    @on(DataTable.RowSelected, "#walls")
    def _apply_selected(self) -> None:
        w = self.selected()
        if w:
            self.message(f"[dim]Applying {w.name}…[/]")
            self._apply(w.path)

    @work(thread=True, exclusive=True, group="apply")
    def _apply(self, path: Path) -> None:
        try:
            notes = self.lp.apply(path)
            msg = f"[green]✓ Now playing {pretty(str(path))}[/]" + "".join(f"  [dim]{n}[/]" for n in notes)
        except BackendError as exc:
            msg = f"[red]{exc}[/]"
        self.call_from_thread(self._after_change, msg)

    def _after_change(self, msg: str) -> None:
        self.message(msg)
        self.refresh_now()
        self.refresh_walls()

    # ── Actions ─────────────────────────────────────────────────────────────
    def action_focus_filter(self) -> None:
        self.query_one("#filter", Input).focus()

    def action_clear_filter(self) -> None:
        f = self.query_one("#filter", Input)
        if f.value:
            f.value = ""
        self.query_one("#walls", DataTable).focus()

    def action_rescan(self) -> None:
        self.refresh_all()
        self.message("[dim]Rescanned the library.[/]")

    def action_random(self) -> None:
        pool = self.shown or self.lp.library.wallpapers()
        if not pool:
            self.message("[yellow]No wallpapers to pick from.[/]")
            return
        import random

        choices = [w for w in pool if w.path != self.lp.current] or pool
        self._apply(random.choice(choices).path)

    def action_stop(self) -> None:
        self._stop()

    @work(thread=True, group="apply")
    def _stop(self) -> None:
        was_running, notes = self.lp.stop()
        msg = "[green]✓ Wallpaper stopped.[/]" if was_running else "[yellow]No wallpaper is running.[/]"
        msg += "".join(f"  [dim]{n}[/]" for n in notes)
        self.call_from_thread(self._after_change, msg)

    def action_favorite(self) -> None:
        w = self.selected()
        if not w:
            return
        on_ = self.lp.state.toggle_favorite(w.path)
        self.message(f"{'★ Added' if on_ else '☆ Removed'} {w.name} {'to' if on_ else 'from'} favourites.")
        self.refresh_categories()
        self.refresh_walls()

    def _target_category(self) -> str:
        return self.view if not self.view.startswith("\x00") else "misc"

    def action_add(self) -> None:
        cat = self._target_category()

        def done(value: str | None) -> None:
            if not value:
                return
            import shlex

            try:
                files = shlex.split(value)
            except ValueError:
                files = [value]
            paths = []
            for f in files:
                p = Path(f).expanduser()
                paths += sorted(p.iterdir()) if p.is_dir() else [p]
            try:
                added = self.lp.library.add(paths, cat)
            except (LibraryError, OSError) as exc:
                self.message(f"[red]{exc}[/]")
                return
            self.message(f"[green]✓ Added {len(added)} wallpaper(s) to {cat}.[/]" if added
                         else "[yellow]No supported files found there.[/]")
            self.refresh_all()

        self.push_screen(Prompt(f"Add files or a folder to “{cat}”",
                                "e.g. ~/Downloads/rain.mp4  or  ~/Videos/loops"), done)

    def action_new_category(self) -> None:
        def done(name: str | None) -> None:
            if not name:
                return
            try:
                name = self.lp.library.create_category(name)
            except (LibraryError, OSError) as exc:
                self.message(f"[red]{exc}[/]")
                return
            self.view = name
            self.refresh_all()
            self.message(f"[green]✓ Created {name}. Press a to add files to it.[/]")

        self.push_screen(Prompt("New category name", "e.g. scenery"), done)

    def action_move(self) -> None:
        w = self.selected()
        if not w:
            return
        options = [c for c in self.lp.library.categories() if c != w.category]

        def done(cat: str | None) -> None:
            if not cat:
                return
            new = self.lp.library.move(w, cat)
            self.lp.state.forget(w.path, new)
            self.message(f"[green]✓ Moved {w.name} to {cat}.[/]")
            self.refresh_all()

        if options:
            self.push_screen(Choose(f"Move “{w.name}” to…", options), done)
        else:
            self.message("[yellow]Create another category first (n).[/]")

    def action_delete(self) -> None:
        w = self.selected()
        if not w:
            return

        def done(yes: bool) -> None:
            if yes:
                self.lp.library.delete(w)
                self.lp.state.forget(w.path)
                self.message(f"Deleted {w.name}.")
                self.refresh_all()

        self.push_screen(Confirm(f"Delete “{w.name}” from disk?\n\n{w.path}", "Delete"), done)

    def action_online(self) -> None:
        def back(_=None) -> None:
            # Downloads may have added wallpapers or categories
            self.refresh_all()

        if self.lp.settings.online_warning_accepted:
            self.push_screen(OnlineScreen(self.lp), back)
            return

        def done(yes: bool) -> None:
            if yes:
                self.lp.settings.online_warning_accepted = True
                self.lp.settings.save()
                self.push_screen(OnlineScreen(self.lp), back)

        self.push_screen(
            Confirm("⚠  Third-party content\n\n" + THIRD_PARTY_WARNING, "I understand, continue", warning=True),
            done,
        )


def run() -> int:
    LimpaperTUI().run()
    return 0
