"""Client for the unified logs API (``GET /v1/projects/{id}/page-logs``).

A single endpoint serves every log-bearing resource: one or many jobs, a whole
deployment (all replicas), every rank of a multi-machine job, and sandbox
commands. Log lines are returned inline and filtered server-side (substring
``query`` and minimum ``severity``), so a caller never fetches and parses log
pages itself. The response also carries a ``follow_url`` websocket -- populated
only while the resource is still active -- for tailing the live stream.

Historical reads are cursor-paginated forward in time; there is no server-side
``tail``, so a bounded tail is applied client-side after paging.
"""

import json
import time
from collections import deque
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any, Callable, Deque, Dict, Iterator, List, Optional, Sequence, Set, Tuple, Union
from urllib.parse import urlparse

from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.rest_client import LightningClient

# While tailing, ``recv()`` is given this timeout so a quiet socket can be re-checked (the server
# holds the connection open with heartbeats rather than closing it). It must stay below the
# server's log-socket heartbeat interval (10s) so ``recv()`` actually wakes up during a lull.
_FOLLOW_POLL_INTERVAL = 5.0

# Budget for the websocket handshake, which can take longer than a read poll.
_CONNECT_TIMEOUT = 30.0

# Look-back windows tried, newest first, when serving a `tail` without an explicit `since`. A
# long-lived resource (a deployment with months of replicas) would otherwise have its whole
# history paged just to keep the last few lines, so start narrow and widen only if needed.
_TAIL_WINDOWS = (
    10 * 60,
    60 * 60,
    6 * 60 * 60,
    24 * 60 * 60,
    7 * 24 * 60 * 60,
)

# Overlap window used to de-duplicate the live tail against the history that was just printed:
# the follow socket starts at "now", so lines written between the last page read and the socket
# being established can arrive twice. Only the most recent history keys can collide, so the set
# is bounded rather than holding every line of a long job.
_MAX_DEDUP_KEYS = 5000

SEVERITIES = ("error", "warning", "info", "debug")


@dataclass(frozen=True)
class LogEntry:
    """One log line, as returned by the logs API or its follow socket."""

    message: str
    timestamp: Optional[datetime] = None
    line: int = 0
    severity: str = ""
    # The job the line came from: the replica for a deployment, the rank for a multi-machine job.
    resource_id: str = ""

    def format(self, *, timestamps: bool = False, prefix: Optional[str] = None) -> str:
        """Render the entry as a printable line.

        Args:
            timestamps: Prepend the entry's ISO-8601 timestamp when it has one.
            prefix: Optional label (e.g. a replica name) to bracket in front of the message.
        """
        parts = []
        if timestamps and self.timestamp is not None:
            parts.append(self.timestamp.isoformat())
        if prefix:
            parts.append(f"[{prefix}]")

        # strip `+ lightning\n` prefix from the message (sometimes returned from the backend)
        parts.append(self.message.removeprefix("+ lightning\n"))

        return " ".join(parts)


    def to_json_dict(self, source: Optional[str] = None) -> "Dict[str, Optional[str]]":
        """Render the entry as a JSON-serializable object; ``source`` labels the replica/rank."""
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp is not None else None,
            "severity": self.severity or None,
            "source": source,
            "message": self.message,
        }

    @property
    def dedup_key(self) -> Tuple[int, Optional[datetime], str]:
        """Identity used to drop a live line that history already produced.

        ``line`` is per-resource, so it is not unique across replicas; combining it with the
        timestamp and message is what the console UI does too.
        """
        return (self.line, self.timestamp, self.message)


@dataclass
class LogsPage:
    """One page of history, plus the follow socket for whatever is still running."""

    entries: List[LogEntry] = field(default_factory=list)
    next_page_token: Optional[str] = None
    # Absent once the resource is finished: there is nothing left to tail.
    follow_url: Optional[str] = None


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """Normalise the timestamp shapes the two transports use into a ``datetime``.

    The REST client deserialises the protobuf ``Timestamp`` into a ``datetime`` already; the
    websocket sends it as ``{"seconds": ..., "nanos": ...}``. An ISO-8601 string is accepted in
    case either representation changes.
    """
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, dict):
        seconds = value.get("seconds")
        if seconds is None:
            return None
        epoch = float(seconds) + float(value.get("nanos", 0)) / 1e9
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    if isinstance(value, str) and value:
        with suppress(ValueError):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _entry_from_model(entry: Any) -> LogEntry:
    """Build a :class:`LogEntry` from a generated ``V1JobLogEntry``."""
    return LogEntry(
        message=str(getattr(entry, "message", "") or ""),
        timestamp=_parse_timestamp(getattr(entry, "timestamp", None)),
        line=_to_int(getattr(entry, "line", 0)),
        severity=str(getattr(entry, "severity", "") or ""),
        resource_id=str(getattr(entry, "resource_id", "") or ""),
    )


def parse_log_entries(payload_text: str) -> List[LogEntry]:
    """Decode a JSON array of log entries into :class:`LogEntry` objects.

    Used for both websocket frames and the bodies of legacy log pages, which share this shape.
    Keys are snake_case (``resource_id``) because the server serialises its protobuf struct
    directly; camelCase is accepted too. Text that is not JSON at all is surfaced line by line so
    nothing is silently dropped.
    """
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return [LogEntry(message=line) for line in payload_text.splitlines()]

    raw_entries = payload if isinstance(payload, list) else [payload]
    entries = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            entries.append(LogEntry(message=str(raw)))
            continue
        entries.append(
            LogEntry(
                message=str(raw.get("message") or raw.get("Message") or ""),
                timestamp=_parse_timestamp(raw.get("timestamp") or raw.get("Timestamp")),
                line=_to_int(raw.get("line")),
                severity=str(raw.get("severity") or ""),
                resource_id=str(raw.get("resource_id") or raw.get("resourceId") or ""),
            )
        )
    return entries


def _websocket_url(url: str) -> str:
    """Return ``url`` as an absolute ``ws(s)://`` URL.

    The server already hands back an absolute ``wss://`` follow URL; a relative or ``http(s)``
    URL is still normalised so the caller does not depend on that.
    """
    if not urlparse(url).netloc:
        url = f"{_get_cloud_url().rstrip('/')}/{url.lstrip('/')}"
    if url.startswith("https://"):
        return "wss://" + url[len("https://") :]
    if url.startswith("http://"):
        return "ws://" + url[len("http://") :]
    return url


class _RecentKeys:
    """Bounded set of the most recently seen entry keys."""

    def __init__(self, maxlen: int = _MAX_DEDUP_KEYS) -> None:
        self._order: Deque[Tuple[int, Optional[datetime], str]] = deque()
        self._keys: Set[Tuple[int, Optional[datetime], str]] = set()
        self._maxlen = maxlen

    def add(self, entry: LogEntry) -> None:
        key = entry.dedup_key
        if key in self._keys:
            return
        self._order.append(key)
        self._keys.add(key)
        while len(self._order) > self._maxlen:
            self._keys.discard(self._order.popleft())

    def __contains__(self, entry: LogEntry) -> bool:
        return entry.dedup_key in self._keys


class LogsApi:
    """Read logs for jobs, deployments, multi-machine jobs and sandbox commands."""

    def __init__(self, client: Optional[LightningClient] = None, api_key: Optional[str] = None) -> None:
        if client is None:
            # A scoped api key (e.g. a sandbox key) authenticates as a bearer token, which the
            # ambient Auth() path does not cover, so inject it directly when one is given.
            client = LightningClient(max_tries=7, with_auth=api_key is None)
            if api_key:
                client.api_client.set_default_header("Authorization", f"Bearer {api_key}")
        self._client = client

    def get_page(
        self,
        teamspace_id: str,
        *,
        job_ids: Sequence[str] = (),
        deployment_id: Optional[str] = None,
        mmt_id: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        sandbox_command_ids: Sequence[str] = (),
        since: Optional[str] = None,
        until: Optional[str] = None,
        query: Optional[str] = None,
        severity: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> LogsPage:
        """Fetch a single page of logs.

        At least one selector (``job_ids``, ``deployment_id``, ``mmt_id``, ``sandbox_id`` or
        ``sandbox_command_ids``) must be given; the server rejects a request without one.

        Args:
            teamspace_id: The teamspace that owns the resource.
            job_ids: Read these jobs, merged into one timeline.
            deployment_id: Read every replica of this deployment.
            mmt_id: Read every rank of this multi-machine job.
            sandbox_id: Read every recorded command of this sandbox.
            sandbox_command_ids: Narrow to specific sandbox commands.
            since: Only include lines at or after this RFC3339 timestamp.
            until: Only include lines at or before this RFC3339 timestamp.
            query: Only include lines containing every whitespace-separated term.
            severity: Only include lines at or above this level (see :data:`SEVERITIES`).
            page_size: Lines per page; the server defaults to 1000.
            page_token: Cursor from a previous page's ``next_page_token``.

        Returns:
            LogsPage: The page's entries, its continuation token and the follow URL.
        """
        kwargs: Dict[str, Any] = {}
        if job_ids:
            kwargs["job_ids"] = list(job_ids)
        if deployment_id:
            kwargs["deployment_id"] = deployment_id
        if mmt_id:
            kwargs["mmt_id"] = mmt_id
        if sandbox_id:
            kwargs["sandbox_id"] = sandbox_id
        if sandbox_command_ids:
            kwargs["sandbox_command_ids"] = list(sandbox_command_ids)
        if since:
            kwargs["since"] = since
        if until:
            kwargs["until"] = until
        if query:
            kwargs["query"] = query
        if severity:
            kwargs["severity"] = severity
        if page_size is not None:
            kwargs["page_size"] = str(page_size)
        if page_token:
            kwargs["page_token"] = page_token

        response = self._client.jobs_service_get_logs(project_id=teamspace_id, **kwargs)
        return LogsPage(
            entries=[_entry_from_model(entry) for entry in (getattr(response, "entries", None) or [])],
            next_page_token=getattr(response, "next_page_token", None) or None,
            follow_url=getattr(response, "follow_url", None) or None,
        )

    def stream(
        self,
        teamspace_id: str,
        *,
        job_ids: Sequence[str] = (),
        deployment_id: Optional[str] = None,
        mmt_id: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        sandbox_command_ids: Sequence[str] = (),
        since: Optional[str] = None,
        until: Optional[str] = None,
        query: Optional[str] = None,
        severity: Optional[str] = None,
        page_size: Optional[int] = None,
        follow: bool = False,
        tail: Optional[int] = None,
        tail_anchor: Optional[Union[datetime, str]] = None,
        idle_timeout: Optional[float] = None,
        fallback_to_live: bool = False,
        stop: Optional[Callable[[], bool]] = None,
    ) -> Iterator[LogEntry]:
        """Yield the resource's history, then optionally tail its live stream.

        Args:
            teamspace_id: The teamspace that owns the resource.
            job_ids: Read these jobs, merged into one timeline.
            deployment_id: Read every replica of this deployment.
            mmt_id: Read every rank of this multi-machine job.
            sandbox_id: Read every recorded command of this sandbox.
            sandbox_command_ids: Narrow to specific sandbox commands.
            since: Only include lines at or after this RFC3339 timestamp.
            until: Only include lines at or before this RFC3339 timestamp.
            query: Only include lines containing every whitespace-separated term.
            severity: Only include lines at or above this level (see :data:`SEVERITIES`).
            page_size: Lines per page; the server defaults to 1000.
            follow: After the history, tail new lines until ``stop`` or interruption.
            tail: Only yield the last N historical lines. The API pages forward only, so this
                reads recent windows first and widens until N lines are found (see
                :data:`_TAIL_WINDOWS`) instead of reading a long history in full.
            tail_anchor: Where that window search ends; defaults to ``until``, else now. Set it to
                a finished resource's stop time so its last lines are found without reading the
                whole history. It bounds the search only, never the lines returned.
            idle_timeout: While tailing, stop after this many seconds without a line.
            fallback_to_live: When the history is empty, tail the live stream even if
                ``follow`` is not set. Used to still show something for a running resource whose
                logs are not in the new storage format yet.
            stop: Called while the tail is quiet; return ``True`` to end the stream.

        Yields:
            LogEntry: History entries in time order, then live entries as they arrive.
        """
        selectors: Dict[str, Any] = {
            "job_ids": job_ids,
            "deployment_id": deployment_id,
            "mmt_id": mmt_id,
            "sandbox_id": sandbox_id,
            "sandbox_command_ids": sandbox_command_ids,
        }
        if not any(selectors.values()):
            raise ValueError("One of job_ids, deployment_id, mmt_id, sandbox_id or sandbox_command_ids is required.")

        filters: Dict[str, Any] = {
            "until": until,
            "query": query,
            "severity": severity,
            "page_size": page_size,
            **selectors,
        }
        recent = _RecentKeys()
        state: Dict[str, Any] = {}
        printed = 0

        if tail:
            tail_entries = self._tail_history(
                teamspace_id, since=since, tail=tail, tail_anchor=tail_anchor, state=state, **filters
            )
            for entry in tail_entries:
                recent.add(entry)
                printed += 1
                yield entry
        else:
            for entry in self._iter_history(teamspace_id, since=since, state=state, **filters):
                recent.add(entry)
                printed += 1
                yield entry

        # Set while paging above, which the loops just drained.
        follow_url = state.get("follow_url")
        if not follow_url:
            return
        if not follow and not (fallback_to_live and printed == 0):
            return

        yield from self.follow(
            follow_url,
            recent=recent,
            idle_timeout=idle_timeout,
            stop=stop,
            reconnect=follow,
        )

    def _iter_history(
        self,
        teamspace_id: str,
        *,
        state: Dict[str, Any],
        **kwargs: Any,
    ) -> Iterator[LogEntry]:
        """Page through the history in time order, recording the first page's follow URL in ``state``."""
        page_token: Optional[str] = None
        while True:
            page = self.get_page(teamspace_id, page_token=page_token, **kwargs)
            if page_token is None:
                state["follow_url"] = page.follow_url
            yield from page.entries
            page_token = page.next_page_token
            if not page_token:
                return

    def _tail_history(
        self,
        teamspace_id: str,
        *,
        tail: int,
        since: Optional[str],
        until: Optional[str] = None,
        tail_anchor: Optional[Union[datetime, str]] = None,
        state: Dict[str, Any],
        **kwargs: Any,
    ) -> List[LogEntry]:
        """Return the last ``tail`` historical lines.

        The API pages forward from the start of the window, so reading a long-lived resource's
        whole history just to keep its last few lines is wasteful. Instead, read a window ending
        at ``until`` (or now) and widen it until enough lines turn up, falling back to the full
        history last. An explicit ``since`` is honoured as-is: the caller already bounded the read.
        """
        page = partial(self._iter_history, teamspace_id, until=until, state=state, **kwargs)
        if since is not None:
            return list(deque(page(since=since), maxlen=tail))

        # Windows end where the logs do, so the last lines of a resource that finished a while
        # ago are found in the first, narrowest window rather than by reading everything. Only
        # the window's lower bound is sent, so a line written after the anchor still shows up.
        anchor = _parse_timestamp(tail_anchor) or _parse_timestamp(until) or datetime.now(timezone.utc)
        if anchor.tzinfo is None:
            # The server only accepts RFC3339, which needs an offset; timestamps here are UTC.
            anchor = anchor.replace(tzinfo=timezone.utc)
        for seconds in (*_TAIL_WINDOWS, None):
            window_start = None if seconds is None else (anchor - timedelta(seconds=seconds)).isoformat()
            entries = deque(page(since=window_start), maxlen=tail)
            if len(entries) >= tail or seconds is None:
                return list(entries)
        return []

    def follow(
        self,
        follow_url: str,
        *,
        recent: Optional[_RecentKeys] = None,
        idle_timeout: Optional[float] = None,
        stop: Optional[Callable[[], bool]] = None,
        reconnect: bool = True,
    ) -> Iterator[LogEntry]:
        """Yield log lines from a ``follow_url`` websocket as they arrive.

        The socket starts at the present moment and stays open (heartbeats only) once the
        resource finishes rather than closing, so a quiet socket is re-checked against ``stop``
        instead of blocking forever. Any ``query``/``severity`` filter is already encoded in the
        URL and applied server-side.

        Args:
            follow_url: The ``follow_url`` from a :class:`LogsPage`.
            recent: Keys of already-yielded history, to drop the replay overlap.
            idle_timeout: Stop after this many seconds without a line.
            stop: Called while the socket is quiet; return ``True`` to end the stream.
            reconnect: Re-establish the socket after a transient drop.

        Yields:
            LogEntry: Live entries in arrival order.
        """
        try:
            import websocket
            from websocket import (
                WebSocketConnectionClosedException,
                WebSocketTimeoutException,
            )
        except ImportError as ex:
            raise RuntimeError(
                "Following logs requires the 'websocket-client' package (pip install websocket-client)."
            ) from ex

        auth_header = Auth().authenticate()
        url = _websocket_url(follow_url)
        # Poll `recv()` rather than blocking on it, so `stop` and `idle_timeout` get a chance to
        # run. The poll has to stay below the server's heartbeat interval: a heartbeat resets the
        # socket's read timeout, so a longer one would never fire. Silence is therefore measured
        # here rather than left to `recv()`.
        recv_timeout = _FOLLOW_POLL_INTERVAL
        if idle_timeout is not None:
            recv_timeout = min(idle_timeout, _FOLLOW_POLL_INTERVAL)
        last_line_at = time.monotonic()

        while True:
            ws = None
            try:
                # The handshake gets a longer budget than the deliberately short read poll.
                ws = websocket.create_connection(
                    url, header=[f"Authorization: {auth_header}"], timeout=_CONNECT_TIMEOUT
                )
                ws.settimeout(recv_timeout)
                while True:
                    try:
                        message = ws.recv()
                    except WebSocketTimeoutException:
                        if idle_timeout is not None and time.monotonic() - last_line_at >= idle_timeout:
                            return  # quiet for long enough: treat the stream as finished
                        if stop is not None and stop():
                            return
                        continue
                    except WebSocketConnectionClosedException:
                        break  # fall through to the reconnect decision
                    if message == "":
                        break
                    entries = parse_log_entries(message)
                    if entries:
                        last_line_at = time.monotonic()
                    for entry in entries:
                        if recent is not None:
                            if entry in recent:
                                continue
                            recent.add(entry)
                        yield entry
            finally:
                if ws is not None:
                    with suppress(Exception):
                        ws.close()

            if not reconnect or idle_timeout is not None:
                return
            if stop is not None and stop():
                return
            time.sleep(1)  # brief backoff, then reconnect and keep tailing
