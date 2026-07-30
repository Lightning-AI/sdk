from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from lightning_sdk.api.logs_api import (
    _CONNECT_TIMEOUT,
    _FOLLOW_POLL_INTERVAL,
    _TAIL_WINDOWS,
    LogEntry,
    LogsApi,
    _websocket_url,
    parse_log_entries,
)
from lightning_sdk.lightning_cloud.openapi import V1GetLogsResponse, V1JobLogEntry


def _api(*pages):
    """A LogsApi whose client returns ``pages`` in order."""
    client = mock.MagicMock()
    client.jobs_service_get_logs.side_effect = list(pages)
    return LogsApi(client=client), client


def _entry(message, *, line=0, resource_id="", severity="", timestamp=None):
    return V1JobLogEntry(message=message, line=line, resource_id=resource_id, severity=severity, timestamp=timestamp)


def test_parse_log_entries_reads_snake_case_frames() -> None:
    entries = parse_log_entries(
        '[{"message":"ready","line":3,"resource_id":"job-1","severity":"info",'
        '"timestamp":{"seconds":1784000000,"nanos":500000000}}]'
    )

    assert len(entries) == 1
    assert entries[0].message == "ready"
    assert entries[0].line == 3
    assert entries[0].resource_id == "job-1"
    assert entries[0].severity == "info"
    assert entries[0].timestamp == datetime.fromtimestamp(1784000000.5, tz=timezone.utc)


def test_parse_log_entries_accepts_camel_case_and_single_objects() -> None:
    entries = parse_log_entries('{"message":"ready","resourceId":"job-1"}')

    assert [(e.message, e.resource_id) for e in entries] == [("ready", "job-1")]


def test_parse_log_entries_falls_back_to_raw_lines() -> None:
    # a frame that is not JSON must still surface rather than being dropped
    assert [e.message for e in parse_log_entries("plain\ntext")] == ["plain", "text"]


def test_parse_log_entries_tolerates_missing_timestamp() -> None:
    assert parse_log_entries('[{"message":"ready"}]')[0].timestamp is None


def test_log_entry_format() -> None:
    entry = LogEntry(message="+ lightning\nready", timestamp=datetime(2026, 7, 27, 9, 0, tzinfo=timezone.utc))

    assert entry.format() == "ready"
    assert entry.format(prefix="replica-0") == "[replica-0] ready"
    assert entry.format(timestamps=True) == "2026-07-27T09:00:00+00:00 ready"
    assert entry.format(timestamps=True, prefix="replica-0") == "2026-07-27T09:00:00+00:00 [replica-0] ready"
    # an entry with no timestamp is printed as-is rather than gaining an empty column
    assert LogEntry(message="ready").format(timestamps=True) == "ready"


def test_websocket_url_preserves_absolute_wss_url() -> None:
    url = "wss://lightning.ai/v1/projects/project-id/logs?follow=true"

    assert _websocket_url(url) == url


def test_websocket_url_upgrades_scheme_and_relative_paths() -> None:
    assert _websocket_url("https://lightning.ai/v1/logs") == "wss://lightning.ai/v1/logs"
    assert _websocket_url("http://localhost:8080/v1/logs") == "ws://localhost:8080/v1/logs"
    assert _websocket_url("/v1/projects/p/logs").endswith("/v1/projects/p/logs")
    assert _websocket_url("/v1/projects/p/logs").startswith("ws")


def test_get_page_maps_selectors_and_filters() -> None:
    api, client = _api(V1GetLogsResponse(entries=[], follow_url="wss://host/logs"))

    page = api.get_page(
        "project-id",
        job_ids=["job-1", "job-2"],
        query="boom",
        severity="error",
        since="2026-07-27T00:00:00Z",
        page_size=250,
    )

    assert page.follow_url == "wss://host/logs"
    kwargs = client.jobs_service_get_logs.call_args.kwargs
    assert kwargs["project_id"] == "project-id"
    assert kwargs["job_ids"] == ["job-1", "job-2"]
    assert kwargs["query"] == "boom"
    assert kwargs["severity"] == "error"
    assert kwargs["since"] == "2026-07-27T00:00:00Z"
    assert kwargs["page_size"] == "250"
    # unset options must not be sent at all
    assert "until" not in kwargs
    assert "deployment_id" not in kwargs
    assert "page_token" not in kwargs


def test_stream_requires_a_selector() -> None:
    api, _ = _api()

    with pytest.raises(ValueError, match="job_ids"):
        list(api.stream("project-id"))


def test_stream_follows_page_tokens() -> None:
    api, client = _api(
        V1GetLogsResponse(entries=[_entry("one")], next_page_token="cursor-1"),
        V1GetLogsResponse(entries=[_entry("two")], next_page_token=""),
    )

    entries = list(api.stream("project-id", deployment_id="dep-id"))

    assert [e.message for e in entries] == ["one", "two"]
    assert client.jobs_service_get_logs.call_count == 2
    assert client.jobs_service_get_logs.call_args_list[1].kwargs["page_token"] == "cursor-1"


def test_stream_tail_keeps_the_last_lines_across_pages() -> None:
    api, _ = _api(
        V1GetLogsResponse(entries=[_entry("a"), _entry("b")], next_page_token="cursor-1"),
        V1GetLogsResponse(entries=[_entry("c"), _entry("d")]),
    )

    entries = list(api.stream("project-id", mmt_id="mmt-id", tail=3))

    # the API only pages forward, so the tail is applied once the history is exhausted
    assert [e.message for e in entries] == ["b", "c", "d"]


def test_stream_tail_widens_the_window_until_enough_lines() -> None:
    api, client = _api(
        # nothing in the most recent window...
        V1GetLogsResponse(entries=[]),
        # ...so the next, wider one is tried
        V1GetLogsResponse(entries=[_entry("a"), _entry("b")]),
    )

    entries = list(api.stream("project-id", deployment_id="dep-id", tail=2))

    assert [e.message for e in entries] == ["a", "b"]
    windows = [call.kwargs["since"] for call in client.jobs_service_get_logs.call_args_list]
    assert len(windows) == 2
    # the second attempt reaches further back than the first
    assert windows[1] < windows[0]


def test_stream_tail_falls_back_to_the_full_history() -> None:
    # every bounded window comes up short, so the last attempt is unbounded
    api, client = _api(*[V1GetLogsResponse(entries=[]) for _ in range(5)], V1GetLogsResponse(entries=[_entry("old")]))

    entries = list(api.stream("project-id", deployment_id="dep-id", tail=5))

    assert [e.message for e in entries] == ["old"]
    assert "since" not in client.jobs_service_get_logs.call_args_list[-1].kwargs


def test_stream_tail_anchor_places_the_window_at_the_stop_time() -> None:
    api, client = _api(V1GetLogsResponse(entries=[_entry("last line")]))
    stopped = datetime(2026, 7, 24, 21, 12, tzinfo=timezone.utc)

    entries = list(api.stream("project-id", job_ids=["job-1"], tail=1, tail_anchor=stopped))

    assert [e.message for e in entries] == ["last line"]
    kwargs = client.jobs_service_get_logs.call_args.kwargs
    # the first window ends at the stop time rather than now, so an old job needs one call
    assert kwargs["since"] == (stopped - timedelta(seconds=_TAIL_WINDOWS[0])).isoformat()
    # the anchor bounds the search only: nothing written after the stop time is filtered out
    assert "until" not in kwargs


def test_stream_tail_honours_an_explicit_since() -> None:
    api, client = _api(V1GetLogsResponse(entries=[_entry("a"), _entry("b"), _entry("c")]))

    entries = list(api.stream("project-id", deployment_id="dep-id", tail=2, since="2026-07-01T00:00:00Z"))

    assert [e.message for e in entries] == ["b", "c"]
    # the caller bounded the read themselves, so no window search happens
    assert client.jobs_service_get_logs.call_count == 1
    assert client.jobs_service_get_logs.call_args.kwargs["since"] == "2026-07-01T00:00:00Z"


def test_stream_does_not_follow_without_a_follow_url() -> None:
    api, _ = _api(V1GetLogsResponse(entries=[_entry("done")], follow_url=""))
    api.follow = mock.MagicMock()

    entries = list(api.stream("project-id", job_ids=["job-1"], follow=True))

    assert [e.message for e in entries] == ["done"]
    # a finished resource has nothing to tail, so no socket is opened
    api.follow.assert_not_called()


def test_stream_tails_after_history_when_following() -> None:
    api, _ = _api(V1GetLogsResponse(entries=[_entry("saved")], follow_url="wss://host/logs"))
    api.follow = mock.MagicMock(return_value=iter([LogEntry(message="live")]))

    entries = list(api.stream("project-id", job_ids=["job-1"], follow=True))

    assert [e.message for e in entries] == ["saved", "live"]
    assert api.follow.call_args.args == ("wss://host/logs",)
    assert api.follow.call_args.kwargs["reconnect"] is True


def test_stream_live_fallback_only_when_history_is_empty() -> None:
    api, _ = _api(
        V1GetLogsResponse(entries=[], follow_url="wss://host/logs"),
        V1GetLogsResponse(entries=[_entry("saved")], follow_url="wss://host/logs"),
    )
    api.follow = mock.MagicMock(return_value=iter([LogEntry(message="live")]))

    empty_history = list(api.stream("project-id", job_ids=["job-1"], fallback_to_live=True, idle_timeout=1))
    assert [e.message for e in empty_history] == ["live"]
    # a one-shot fallback must not reconnect once the socket goes quiet
    assert api.follow.call_args.kwargs["reconnect"] is False

    api.follow.reset_mock()
    with_history = list(api.stream("project-id", job_ids=["job-1"], fallback_to_live=True, idle_timeout=1))
    assert [e.message for e in with_history] == ["saved"]
    api.follow.assert_not_called()


class _FakeSocket:
    def __init__(self, frames):
        self._frames = list(frames)
        self.closed = False
        self.timeout = None

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self):
        if not self._frames:
            raise _FakeTimeoutError
        frame = self._frames.pop(0)
        if isinstance(frame, Exception):
            raise frame
        return frame

    def close(self):
        self.closed = True


class _FakeTimeoutError(Exception):
    pass


class _FakeClosedError(Exception):
    pass


@pytest.fixture()
def fake_websocket(monkeypatch):
    """Stand in for the websocket-client module used by ``LogsApi.follow``."""
    module = mock.MagicMock()
    module.WebSocketTimeoutException = _FakeTimeoutError
    module.WebSocketConnectionClosedException = _FakeClosedError
    monkeypatch.setitem(__import__("sys").modules, "websocket", module)
    monkeypatch.setattr("lightning_sdk.api.logs_api.Auth", mock.MagicMock())
    return module


def test_follow_yields_frames_until_idle(fake_websocket) -> None:
    socket = _FakeSocket(['[{"message":"live-1"},{"message":"live-2"}]'])
    fake_websocket.create_connection.return_value = socket

    entries = list(LogsApi(client=mock.MagicMock()).follow("wss://host/logs", idle_timeout=1))

    assert [e.message for e in entries] == ["live-1", "live-2"]
    assert socket.closed
    # the handshake gets its own budget; the read poll is set on the socket afterwards
    assert fake_websocket.create_connection.call_args.kwargs["timeout"] == _CONNECT_TIMEOUT
    assert socket.timeout == 1


def test_follow_polls_below_the_server_heartbeat(fake_websocket) -> None:
    fake_websocket.create_connection.return_value = _FakeSocket([])

    # a heartbeat resets the socket read timeout, so the poll must stay short and the silence
    # be measured by the caller instead
    with mock.patch("lightning_sdk.api.logs_api.time.monotonic", side_effect=[0.0, 0.0, 61.0]):
        list(LogsApi(client=mock.MagicMock()).follow("wss://host/logs", idle_timeout=60))

    assert fake_websocket.create_connection.return_value.timeout == _FOLLOW_POLL_INTERVAL


def test_follow_keeps_waiting_while_lines_keep_arriving(fake_websocket) -> None:
    fake_websocket.create_connection.return_value = _FakeSocket(
        ['[{"message":"one"}]', _FakeTimeoutError(), '[{"message":"two"}]']
    )
    clock = [0.0, 0.0, 1.0, 1.0, 1.0, 99.0, 99.0, 99.0]

    with mock.patch("lightning_sdk.api.logs_api.time.monotonic", side_effect=clock):
        entries = list(LogsApi(client=mock.MagicMock()).follow("wss://host/logs", idle_timeout=5))

    # the gap between the two lines is under the idle timeout, so the stream survives it
    assert [e.message for e in entries] == ["one", "two"]


def test_follow_stops_when_the_resource_finishes(fake_websocket) -> None:
    fake_websocket.create_connection.return_value = _FakeSocket(['[{"message":"live"}]'])

    entries = list(LogsApi(client=mock.MagicMock()).follow("wss://host/logs", stop=lambda: True))

    # the socket stays open (heartbeats only) after the resource ends, so `stop` ends the stream
    assert [e.message for e in entries] == ["live"]


def test_follow_drops_lines_already_seen_in_history(fake_websocket) -> None:
    api, _ = _api(
        V1GetLogsResponse(entries=[_entry("saved", line=1)], follow_url="wss://host/logs"),
    )
    # the live socket starts at "now" and replays the line history just produced
    fake_websocket.create_connection.return_value = _FakeSocket(
        ['[{"message":"saved","line":1},{"message":"new","line":2}]']
    )

    entries = list(api.stream("project-id", job_ids=["job-1"], follow=True, idle_timeout=1))

    assert [e.message for e in entries] == ["saved", "new"]


def test_follow_reconnects_after_a_drop(fake_websocket) -> None:
    sockets = [
        _FakeSocket(['[{"message":"before"}]', _FakeClosedError()]),
        _FakeSocket(['[{"message":"after"}]']),
    ]
    fake_websocket.create_connection.side_effect = sockets
    stop = mock.MagicMock(side_effect=[False, True])

    with mock.patch("lightning_sdk.api.logs_api.time.sleep"):
        entries = list(LogsApi(client=mock.MagicMock()).follow("wss://host/logs", stop=stop))

    assert [e.message for e in entries] == ["before", "after"]
    assert fake_websocket.create_connection.call_count == 2


def test_follow_requires_websocket_client(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "websocket":
            raise ImportError("no websocket-client")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="websocket-client"):
        list(LogsApi(client=mock.MagicMock()).follow("wss://host/logs"))
