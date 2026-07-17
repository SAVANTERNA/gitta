from __future__ import annotations
import subprocess
from dataclasses import dataclass
from typing import List, Tuple, Optional
from pathlib import Path
import os


def _run_git(*args: str) -> Tuple[int, str, str]:
    p = subprocess.run(["git", *args], text=True, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def _get_status() -> str:
    code, out, err = _run_git("status", "--porcelain=v1", "-b")
    if code != 0:
        return err or "Not a git repository."
    return out


def _get_graph() -> str:
    code, out, err = _run_git("log", "--graph", "--oneline", "--decorate", "--all", "--color=never")
    if code != 0:
        return err or "(no commits)"
    return out


def _get_diff(path: str | None) -> str:
    args = ["diff"]
    if path:
        args.append(path)
    code, out, err = _run_git(*args)
    if code not in (0, 1):  # diff returns 1 when differences found
        return err
    return out


THEMES = ["dark", "light", "dracula"]


def _read_builtin_css(name: str) -> Optional[str]:
    base = Path(__file__).parent / "themes" / f"{name}.css"
    if base.exists():
        return base.read_text(encoding="utf-8")
    return None


def run(theme: Optional[str] = None, css_path: Optional[str] = None) -> int:
    # Lazy import to avoid hard dependency if Textual not installed
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Static, TabbedContent, TabPane, Tabs, Input, Button
    from textual.containers import Horizontal, Vertical
    from textual import on

    class StatusView(Static):
        def on_mount(self) -> None:
            self.update(_get_status())

        def refresh_data(self) -> None:
            self.update(_get_status())

    class GraphView(Static):
        def on_mount(self) -> None:
            self.update(_get_graph())

        def refresh_data(self) -> None:
            self.update(_get_graph())

    class DiffView(Static):
        current_path: str | None = None

        def on_mount(self) -> None:
            self.update("(Välj fil i CLI för diff, eller använd gitta diff)")

        def show_path(self, path: str | None) -> None:
            self.current_path = path
            self.update(_get_diff(path))

    class GittaApp(App):
        CSS = "Screen { layout: vertical; } #body { layout: horizontal; }"
        BINDINGS = [
            ("q", "quit", "Quit"),
            ("r", "refresh", "Refresh"),
            ("g", "graph", "Graph"),
            ("s", "status", "Status"),
            ("d", "diff", "Diff"),
            ("t", "toggle_theme", "Theme"),
        ]

        _theme_name: str = theme or os.environ.get("GITTA_TUI_THEME", "dark")

        def compose(self) -> ComposeResult:
            yield Header()
            with Horizontal(id="body"):
                # Right side: tabs
                with Vertical(classes="panel"):
                    tabs = TabbedContent(
                        TabPane(StatusView(id="status"), title="Status"),
                        TabPane(GraphView(id="graph"), title="Graph"),
                        TabPane(DiffView(id="diff"), title="Diff"),
                    )
                    yield tabs
            yield Footer()

        def on_mount(self) -> None:
            # Load CSS from explicit file or built-in theme
            if css_path:
                try:
                    self.load_css(css_path)
                except Exception as e:
                    self.bell()
            else:
                css = _read_builtin_css(self._theme_name)
                if css:
                    self.stylesheet.read(css, path=f"builtin:{self._theme_name}")

        def action_refresh(self) -> None:
            self.query_one(StatusView).refresh_data()
            self.query_one(GraphView).refresh_data()
            d = self.query_one(DiffView)
            if d.current_path:
                d.show_path(d.current_path)

        def action_graph(self) -> None:
            self.query_one(TabbedContent).active = 1

        def action_status(self) -> None:
            self.query_one(TabbedContent).active = 0

        def action_diff(self) -> None:
            self.query_one(TabbedContent).active = 2

        def action_toggle_theme(self) -> None:
            # Cycle themes if using built-ins
            if css_path:
                return
            try:
                idx = THEMES.index(self._theme_name)
            except ValueError:
                idx = -1
            self._theme_name = THEMES[(idx + 1) % len(THEMES)]
            css = _read_builtin_css(self._theme_name)
            if css:
                self.stylesheet.read(css, path=f"builtin:{self._theme_name}")
                self.refresh()

    return GittaApp().run()
