"""Textual TUI application for interactive SDK log viewing."""

from __future__ import annotations

import socket
import threading
from collections import deque
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar, Dict, Optional

from rich.spinner import Spinner
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
)

from lightning_sdk.api.logs_api import LogEntry, LogsApi
from lightning_sdk.cli.utils.logs import LogSelection

_BACKFILL_TRIGGER_ROW = 2
_MATCH_COLOR = "#f3e8ff"
_PAGE_LINES = 200
_TAIL_WINDOWS = (
    10 * 60,
    60 * 60,
    6 * 60 * 60,
    24 * 60 * 60,
    7 * 24 * 60 * 60,
)


def _dedup_key(resource_id: str, line_no: int) -> tuple[str, int]:
    return (resource_id, line_no)


@dataclass
class LogLine:
    timestamp: datetime | None = None
    message: str = ""
    line_no: int = 0
    resource_id: str = ""
    live: bool = False

    @classmethod
    def from_entry(cls, entry: LogEntry, source: str | None = None) -> LogLine:
        return cls(
            timestamp=entry.timestamp,
            message=entry.message,
            line_no=entry.line,
            resource_id=entry.resource_id,
        )

    @property
    def key(self) -> tuple[str, int]:
        return _dedup_key(self.resource_id, self.line_no)


class ConnectingIndicator(Static):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self._spinner = Spinner("dots", text=Text("Connecting…", style="dim"), style="#c084fc")

    def on_mount(self) -> None:
        self.display = False
        self.set_interval(1 / 12, self._tick)

    def _tick(self) -> None:
        if self.display:
            self.update(self._spinner)


class FilterScreen(ModalScreen[Optional[Dict[str, Any]]]):
    """Modal dialog for setting log filters."""

    DEFAULT_CSS = """
    FilterScreen {
        align: center middle;
    }
    #filter-dialog {
        width: 60;
        height: auto;
        min-height: 18;
        max-height: 90%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
        padding-bottom: 2;
        overflow: auto;
    }
    #filter-title {
        text-align: center;
        padding-bottom: 1;
        border-bottom: solid $primary-darken-3;
        margin-bottom: 1;
    }
    #filter-buttons {
        height: auto;
        margin-top: 1;
        align: right middle;
    }
    #filter-buttons Button {
        margin-left: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss(None)", "Cancel", key_display="Esc"),
        Binding("enter", "apply", "Apply"),
        Binding("ctrl+c", "dismiss_all_and_quit", "Quit"),
    ]

    def action_dismiss_all_and_quit(self) -> None:
        """Dismiss the modal and quit the entire app."""
        self.app.exit()

    def __init__(self, current: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._current = current or {}

    def compose(self) -> ComposeResult:
        with Vertical(id="filter-dialog"):
            yield Label("[bold]Filter Logs[/bold]", id="filter-title")
            yield Label("Search query:", id="filter-query-label")
            yield Input(
                placeholder="e.g. error timeout",
                id="filter-query",
                value=self._current.get("query", ""),
            )
            yield Label("Since (e.g. 2h, 30m):", id="filter-since-label")
            yield Input(
                placeholder="e.g. 2h",
                id="filter-since",
                value=self._current.get("since", ""),
            )
            yield Label("Until (e.g. 1h, 15m):", id="filter-until-label")
            yield Input(
                placeholder="e.g. 1h",
                id="filter-until",
                value=self._current.get("until", ""),
            )
            with Horizontal(id="filter-buttons"):
                yield Button("Cancel", variant="default", id="filter-cancel")
                yield Button("Apply", variant="primary", id="filter-apply")

    def on_mount(self) -> None:
        self.call_after_refresh(lambda: self.query_one("#filter-dialog").scroll_home(animate=False))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "filter-apply":
            self.action_apply()
        else:
            self.dismiss(None)

    def action_apply(self) -> None:
        query = self.query_one("#filter-query", Input).value.strip()
        since = self.query_one("#filter-since", Input).value.strip()
        until = self.query_one("#filter-until", Input).value.strip()

        result: dict[str, Any] = {}
        if query:
            result["query"] = query
        if since:
            result["since"] = since
        if until:
            result["until"] = until
        self.dismiss(result if result else None)


class HelpScreen(ModalScreen[None]):
    """Keyboard shortcut reference."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("ctrl+c", "dismiss_all_and_quit", "Quit"),
    ]

    def action_dismiss_all_and_quit(self) -> None:
        """Dismiss the modal and quit the entire app."""
        self.app.exit()

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]Keyboard Shortcuts[/bold]\n\n"
            "  [bold]f[/bold]         Filter/search (or clear an active filter)\n"
            "  [bold]l[/bold]         Toggle autoscroll (live follow)\n"
            "  [bold]t[/bold]         Toggle timestamps\n"
            "  [bold]g[/bold]         Jump to start of logs\n"
            "  [bold]G[/bold]         Scroll to bottom (newest)\n"
            "  [bold]q / Ctrl+C[/bold] Quit\n"
            "  [bold]?[/bold]         This help\n\n"
            "[dim]Press Esc to close[/dim]",
            id="help-body",
        )


class LogsTUI(App[None]):
    """Interactive TUI for browsing and streaming SDK logs."""

    CSS = """
    Screen { layout: grid; grid-size: 1; grid-rows: auto 1fr auto auto; }
    #status-bar { height: 1; background: $surface; padding: 0 1; }
    #log-table { height: 100%; min-height: 5; }
    #connecting { width: auto; margin-right: 1; }
    #line-count { color: $text-muted; }
    #filter-summary { color: #e9d5ff; margin-left: 2; }

    Footer { display: none; }
    #main-footer { display: block; }

    HelpScreen > Static { width: 44; height: auto; background: $surface;
                          border: solid $primary; padding: 1 2; margin: 2 4; }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("/", "toggle_filter", "Filter"),
        Binding("l", "toggle_follow", "Live"),
        Binding("t", "toggle_timestamps", "Timestamps"),
        Binding("g", "scroll_top", "Top"),
        Binding("G", "scroll_bottom", "Bottom"),
        Binding("shift+g", "scroll_bottom", "Bottom"),
        Binding("question_mark", "show_help", "Help"),
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    show_timestamps: reactive[bool] = reactive(True)
    total_lines: reactive[int] = reactive(0)
    filter_active: reactive[bool] = reactive(False)

    def __init__(
        self,
        selection: LogSelection,
        *,
        show_timestamps: bool = True,
        follow: bool = False,
        tail: int | None = None,
        query: str | None = None,
        since: str | None = None,
        until: str | None = None,
        api_key: str | None = None,
        title: str | None = None,
    ) -> None:
        super().__init__()
        if title:
            self.title = title
        self._selection = selection
        self._follow = follow
        self._tail = tail
        self._page_lines = tail if (tail and tail > 0) else _PAGE_LINES
        self._query = query
        self._since = since
        self._until = until
        self._api_key = api_key
        self._lines: list[LogLine] = []
        self._paused = not follow
        self._autoscroll = follow
        self._initial_timestamps = show_timestamps
        self._oldest_ts: datetime | None = None
        self._history_loaded = False
        self._loading_older = False
        self._backfill_done = False
        self._at_start = False
        self._pending_start = False
        self._follow_url: str | None = None
        self._pending: list[LogLine] = []
        self._pending_lock = threading.Lock()
        self._follow_ws: Any = None
        self._follow_ws_lock = threading.Lock()
        self._live_started = False
        self._pending_bottom_scroll = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DataTable(id="log-table", cursor_type="row", zebra_stripes=True)
        with Vertical(id="status-bar"), Horizontal():
            yield ConnectingIndicator(id="connecting")
            yield Label("", id="line-count")
            yield Label("", id="filter-summary")
        yield Footer(id="main-footer")

    def on_mount(self) -> None:
        # Register and apply a custom purple theme.
        self.register_theme(
            Theme(
                name="logs-purple",
                primary="#a78bfa",
                secondary="#7c3aed",
                accent="#c084fc",
                warning="#d8b4fe",
                error="#a855f7",
                success="#e9d5ff",
                foreground="#e0e0e0",
                surface="#1e1e24",
                dark=True,
                variables={
                    "footer-key-foreground": "#c084fc",
                },
            )
        )
        self.theme = "logs-purple"
        self._update_status_bar()
        self.set_interval(0.12, self._flush_pending)
        self._load_history()
        self.show_timestamps = self._initial_timestamps
        self._sync_follow_binding()

    def exit(self, *args: Any, **kwargs: Any) -> None:
        self._paused = True
        self._shutdown_follow_socket()
        super().exit(*args, **kwargs)

    def _register_follow_socket(self, ws: Any) -> None:
        with self._follow_ws_lock:
            self._follow_ws = ws

    def _shutdown_follow_socket(self) -> None:
        with self._follow_ws_lock:
            ws = self._follow_ws
        sock = getattr(ws, "sock", None)
        if sock is not None:
            with suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)

    def watch_show_timestamps(self, value: bool) -> None:
        self._sync_timestamp_binding()
        self._reconfigure_columns()
        if self._lines:
            self._rebuild_table()

    def _sync_timestamp_binding(self) -> None:
        description = "Hide timestamps" if self.show_timestamps else "Show timestamps"
        bindings = self._bindings.key_to_bindings.get("t", [])
        for i, binding in enumerate(bindings):
            if binding.action == "toggle_timestamps":
                bindings[i] = replace(binding, description=description)
        self.refresh_bindings()

    def watch_total_lines(self) -> None:
        self._update_status_bar()

    def watch_filter_active(self) -> None:
        self._sync_filter_binding()
        self._update_status_bar()

    def _fetch_tail(self, api: LogsApi, *, until: datetime | None = None) -> tuple[list[LogEntry], str | None]:
        user_since = self._resolve_time(self._since)
        until_iso = until.isoformat() if until is not None else self._resolve_time(self._until)
        anchor = until if until is not None else datetime.now(timezone.utc)

        if user_since is not None:
            lower_bounds = [user_since]
        else:
            lower_bounds = [(anchor - timedelta(seconds=w)).isoformat() for w in _TAIL_WINDOWS]

        entries: list[LogEntry] = []
        follow_url: str | None = None
        for since_iso in lower_bounds:
            window: deque[LogEntry] = deque(maxlen=self._page_lines)
            page_token: str | None = None
            window_follow_url: str | None = None
            while True:
                page = api.get_page(
                    self._selection.teamspace_id,
                    since=since_iso,
                    until=until_iso,
                    query=self._query,
                    page_token=page_token,
                    job_ids=self._selection.job_ids,
                    deployment_id=self._selection.deployment_id,
                    mmt_id=self._selection.mmt_id,
                    sandbox_id=self._selection.sandbox_id,
                    sandbox_command_ids=self._selection.sandbox_command_ids,
                )
                if page_token is None:
                    window_follow_url = page.follow_url
                window.extend(page.entries)
                page_token = page.next_page_token
                if not page_token:
                    break
            entries, follow_url = list(window), window_follow_url
            if len(entries) >= self._page_lines:
                break
        return entries, follow_url

    @work(exclusive=True, thread=True)
    def _load_history(self) -> None:
        api = LogsApi(api_key=self._api_key)
        try:
            entries, follow_url = self._fetch_tail(api)
        except (RuntimeError, ConnectionError, OSError) as exc:
            self._lines = [LogLine(timestamp=datetime.now(timezone.utc), message=f"Failed to load logs: {exc}")]
            self._backfill_done = True
            self.call_from_thread(self._finish_initial_load)
            return
        self._follow_url = follow_url
        labels = self._selection.labels
        self._lines = [LogLine.from_entry(e, labels.get(e.resource_id) if labels else None) for e in entries]
        self._oldest_ts = self._lines[0].timestamp if self._lines else None
        self._backfill_done = len(entries) < self._page_lines or self._oldest_ts is None
        self.call_from_thread(self._finish_initial_load)

    def _finish_initial_load(self) -> None:
        self._rebuild_table()
        self._history_loaded = True
        if self._follow:
            self._start_follow()
        self._maybe_start_pending()

    @work(thread=True, group="backfill")
    def _load_older(self) -> None:
        oldest = self._oldest_ts
        if oldest is None:
            self.call_from_thread(self._apply_backfill, [], 0, True)
            return
        api = LogsApi(api_key=self._api_key)
        entries: list[LogEntry] = []
        error = False
        try:
            entries, _ = self._fetch_tail(api, until=oldest)
        except (RuntimeError, ConnectionError, OSError):
            error = True
        labels = self._selection.labels
        existing = {ln.key for ln in self._lines}
        older = [
            LogLine.from_entry(e, labels.get(e.resource_id) if labels else None)
            for e in entries
            if _dedup_key(e.resource_id, e.line) not in existing
        ]
        self.call_from_thread(self._apply_backfill, older, len(entries), error)

    @work(thread=True, group="backfill")
    def _load_start(self) -> None:
        api = LogsApi(api_key=self._api_key)
        entries: list[LogEntry] = []
        error = False
        try:
            page = api.get_page(
                self._selection.teamspace_id,
                query=self._query,
                page_size=self._page_lines,
                job_ids=self._selection.job_ids,
                deployment_id=self._selection.deployment_id,
                mmt_id=self._selection.mmt_id,
                sandbox_id=self._selection.sandbox_id,
                sandbox_command_ids=self._selection.sandbox_command_ids,
            )
            entries = page.entries
        except (RuntimeError, ConnectionError, OSError):
            error = True
        labels = self._selection.labels
        existing = {ln.key for ln in self._lines}
        oldest = [
            LogLine.from_entry(e, labels.get(e.resource_id) if labels else None)
            for e in entries
            if _dedup_key(e.resource_id, e.line) not in existing
        ]
        self.call_from_thread(self._apply_start, oldest, error)

    def _apply_start(self, oldest: list[LogLine], error: bool) -> None:
        self._loading_older = False
        self._pending_start = False
        if error:
            self._update_status_bar()
            return
        self._at_start = True
        self._backfill_done = True
        table = self.query_one("#log-table", DataTable)
        if oldest:
            self._lines = oldest + self._lines
            self._oldest_ts = self._lines[0].timestamp
            self._rebuild_table(scroll_to_end=False)
        if table.row_count > 0:
            table.move_cursor(row=0, animate=False, scroll=False)
        self.call_after_refresh(lambda: table.scroll_home(animate=False))
        self._update_status_bar()

    @work(exclusive=True, thread=True)
    def _start_follow(self) -> None:
        self._paused = False
        self._live_started = False
        self.call_from_thread(self._on_follow_state_changed)
        api = LogsApi(api_key=self._api_key)
        labels = self._selection.labels
        try:
            follow_url = self._follow_url
            if not follow_url:
                # cheap single request to obtain the live socket URL
                page = api.get_page(
                    self._selection.teamspace_id,
                    query=self._query,
                    page_size=1,
                    job_ids=self._selection.job_ids,
                    deployment_id=self._selection.deployment_id,
                    mmt_id=self._selection.mmt_id,
                    sandbox_id=self._selection.sandbox_id,
                    sandbox_command_ids=self._selection.sandbox_command_ids,
                )
                follow_url = page.follow_url
                self._follow_url = follow_url
            if not follow_url:
                return
            seen = {ln.key for ln in self._lines}
            for entry in api.follow(
                follow_url,
                idle_timeout=None,
                stop=lambda: self._paused,
                reconnect=True,
                on_socket=self._register_follow_socket,
            ):
                if self._paused:
                    break
                key = _dedup_key(entry.resource_id, entry.line)
                if key in seen:
                    continue
                seen.add(key)
                self._queue_live_line(LogLine.from_entry(entry, labels.get(entry.resource_id) if labels else None))
        except (RuntimeError, ConnectionError, OSError) as exc:
            self._queue_live_line(LogLine(timestamp=datetime.now(timezone.utc), message=f"Live stream error: {exc}"))
        finally:
            self._paused = True
            with suppress(RuntimeError):
                self.call_from_thread(self._on_follow_state_changed)

    def _reconfigure_columns(self) -> None:
        """Add or remove the Timestamp column based on show_timestamps."""
        table = self.query_one("#log-table", DataTable)
        table.clear(columns=True)
        table.add_column("Line", width=6)
        if self.show_timestamps:
            table.add_column("Timestamp", width=22)
        table.add_column("Message")

    def _rebuild_table(self, *, scroll_to_end: bool = True) -> None:
        table = self.query_one("#log-table", DataTable)
        table.clear()
        query_terms = self._query.split() if self._query else []
        show_ts = self.show_timestamps
        for idx, line in enumerate(self._lines, start=1):
            table.add_row(*self._render_cells(idx, line, query_terms, show_ts))
        self.total_lines = len(self._lines)
        if scroll_to_end:
            self._scroll_to_bottom()

    def _render_cells(self, idx: int, line: LogLine, query_terms: list[str], show_ts: bool) -> list[Any]:
        raw = line.message.replace("\r\n", " ").replace("\n", " ").replace("\r", "")
        message = Text.from_ansi(raw)
        if query_terms:
            message.highlight_words(query_terms, f"bold {_MATCH_COLOR}", case_sensitive=False)
        cells: list[Any] = ["" if line.live else str(idx)]
        if show_ts:
            cells.append(self._format_timestamp(line.timestamp))
        cells.append(message)
        return cells

    @staticmethod
    def _format_timestamp(ts: datetime | None) -> str:
        if ts is None:
            return ""
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone().strftime("%Y-%m-%d %H:%M:%S")

    @on(DataTable.RowHighlighted)
    def _maybe_backfill(self, event: DataTable.RowHighlighted) -> None:
        table = self.query_one("#log-table", DataTable)
        cursor_row = table.cursor_row
        if cursor_row is not None and cursor_row <= _BACKFILL_TRIGGER_ROW and not self._is_at_bottom(table):
            self._loading_older = True
            self._update_status_bar()
            self._load_older()

    def _apply_backfill(self, older: list[LogLine], fetched: int, error: bool) -> None:
        self._loading_older = False
        self._maybe_start_pending()
        if error:
            self._update_status_bar()
            return
        if fetched < self._page_lines or not older:
            self._backfill_done = True
        if not older:
            self._update_status_bar()
            return
        table = self.query_one("#log-table", DataTable)
        prev_row = table.cursor_row or 0
        prev_scroll_y = table.scroll_offset.y
        added = len(older)
        self._lines = older + self._lines
        self._oldest_ts = self._lines[0].timestamp
        if self._oldest_ts is None:
            self._backfill_done = True
        self._rebuild_table(scroll_to_end=False)
        if table.row_count > 0:
            table.move_cursor(row=min(prev_row + added, table.row_count - 1), animate=False, scroll=False)
        self.call_after_refresh(lambda: table.scroll_to(y=prev_scroll_y + added, animate=False))
        self._update_status_bar()

    def _flush_pending(self) -> None:
        with self._pending_lock:
            if not self._pending:
                return
            batch = self._pending
            self._pending = []
        table = self.query_one("#log-table", DataTable)
        stick = self._autoscroll and self._is_at_bottom(table)
        query_terms = self._query.split() if self._query else []
        show_ts = self.show_timestamps
        for line in batch:
            self._lines.append(line)
            table.add_row(*self._render_cells(len(self._lines), line, query_terms, show_ts))
        self.total_lines = len(self._lines)
        if not self._live_started:
            self._live_started = True
            self._update_status_bar()
        if stick:
            self._scroll_to_bottom()

    def _queue_live_line(self, line: LogLine) -> None:
        line.live = True
        with self._pending_lock:
            self._pending.append(line)

    @staticmethod
    def _is_at_bottom(table: DataTable) -> bool:
        if table.max_scroll_y <= 0:
            return True
        return table.scroll_offset.y >= table.max_scroll_y - 1

    def _scroll_to_bottom(self) -> None:
        table = self.query_one("#log-table", DataTable)
        if table.row_count == 0:
            return

        self._pending_bottom_scroll = True

        def _do_scroll() -> None:
            table.move_cursor(row=table.row_count - 1, animate=False)
            table.scroll_end(animate=False)
            self._pending_bottom_scroll = False

        self.call_after_refresh(_do_scroll)

    def _update_status_bar(self) -> None:
        line_count = self.query_one("#line-count", Label)
        filter_sum = self.query_one("#filter-summary", Label)

        self.query_one("#connecting", ConnectingIndicator).display = not self._paused and not self._live_started

        if self._loading_older:
            line_count.update(f"Lines: {self.total_lines} [dim]⟳ loading older…[/dim]")
        elif self._backfill_done and self._history_loaded and (self._live_started or self._paused):
            line_count.update(f"Lines: {self.total_lines} [dim](start of logs)[/dim]")
        elif not self._live_started and not self._paused and self.total_lines == 0:
            line_count.update("")
        else:
            line_count.update(f"Lines: {self.total_lines}")

        filters = []
        if self._query:
            filters.append(f'"{self._query}"')
        if self._since:
            filters.append(f"since={self._since}")
        if self._until:
            filters.append(f"until={self._until}")
        if filters:
            filter_sum.update(f"[#e9d5ff]🔍 {' | '.join(filters)}[/]")
            self.filter_active = True
        else:
            filter_sum.update("")
            self.filter_active = False

    def _on_follow_state_changed(self) -> None:
        self._sync_follow_binding()
        self._update_status_bar()

    def _sync_follow_binding(self) -> None:
        description = "Disable autoscroll" if self._autoscroll else "Enable autoscroll"
        bindings = self._bindings.key_to_bindings.get("l", [])
        for i, binding in enumerate(bindings):
            if binding.action == "toggle_follow":
                bindings[i] = replace(binding, description=description)
        self.refresh_bindings()

    def action_toggle_follow(self) -> None:
        self._autoscroll = not self._autoscroll
        if self._autoscroll:
            if self._paused:
                self._start_follow()
            self._scroll_to_bottom()
        self._on_follow_state_changed()

    def action_toggle_timestamps(self) -> None:
        self.show_timestamps = not self.show_timestamps

    def action_toggle_filter(self) -> None:
        if self.filter_active:
            self._apply_filters({})  # {} == clear all filters
            return
        current = {}
        if self._query:
            current["query"] = self._query
        if self._since:
            current["since"] = self._since
        if self._until:
            current["until"] = self._until
        self.push_screen(FilterScreen(current), self._apply_filters)

    def _sync_filter_binding(self) -> None:
        description = "Clear filter" if self.filter_active else "Filter"
        bindings = self._bindings.key_to_bindings.get("f", [])
        for i, binding in enumerate(bindings):
            if binding.action == "toggle_filter":
                bindings[i] = replace(binding, description=description)
        self.refresh_bindings()

    def _apply_filters(self, result: dict[str, Any] | None) -> None:
        if result is None:
            return
        new_query = result.get("query")
        new_since = result.get("since")
        new_until = result.get("until")
        if (new_query, new_since, new_until) == (self._query, self._since, self._until):
            return  # nothing changed, skip reload
        self._paused = True
        self._query = new_query
        self._since = new_since
        self._until = new_until
        self._lines = []
        self._oldest_ts = None
        self._history_loaded = False
        self._loading_older = False
        self._backfill_done = False
        self._at_start = False
        self._pending_start = False
        self._follow_url = None
        self._rebuild_table()
        self._load_history()
        self._update_status_bar()

    def action_scroll_top(self) -> None:
        table = self.query_one("#log-table", DataTable)
        if table.row_count > 0:
            table.move_cursor(row=0, animate=False)
        if self._at_start:
            return
        if not self._history_loaded or self._loading_older:
            self._pending_start = True
            return
        self._start_from_top()

    def _start_from_top(self) -> None:
        """Kick off the page-0 fetch that reaches the true start of the logs."""
        self._pending_start = False
        self._loading_older = True
        self._update_status_bar()
        self._load_start()

    def _maybe_start_pending(self) -> None:
        """Honour a `g` that arrived before the buffer was ready to fetch page 0."""
        if self._pending_start and not self._at_start and self._history_loaded and not self._loading_older:
            self._start_from_top()

    def action_scroll_bottom(self) -> None:
        table = self.query_one("#log-table", DataTable)
        if table.row_count > 0:
            table.move_cursor(row=table.row_count - 1)

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    @staticmethod
    def _resolve_time(value: str | None) -> str | None:
        if not value:
            return None
        try:
            from lightning_sdk.cli.utils.logs import resolve_time

            return resolve_time(value, "")
        except Exception:
            return value


def run_tui(
    selection: LogSelection,
    *,
    show_timestamps: bool = True,
    follow: bool = False,
    tail: int | None = None,
    query: str | None = None,
    since: str | None = None,
    until: str | None = None,
    api_key: str | None = None,
    title: str | None = None,
) -> None:
    app = LogsTUI(
        selection,
        show_timestamps=show_timestamps,
        follow=follow,
        tail=tail,
        query=query,
        since=since,
        until=until,
        api_key=api_key,
        title=title,
    )
    app.run()
