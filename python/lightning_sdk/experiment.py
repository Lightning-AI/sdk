"""Read handle for a LitLogger experiment run in a teamspace."""

import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Iterable, Iterator, List, Optional, Tuple, Union

from lightning_sdk.api.lit_logger_api import LitLoggerApi
from lightning_sdk.lightning_cloud.openapi import V1MetricsStream
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.utils.logging import TrackCallsMeta
from lightning_sdk.utils.resolve import _resolve_teamspace

if TYPE_CHECKING:
    from lightning_sdk.organization import Organization
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

__all__ = ["Experiment"]

_FOLLOW_POLL_INTERVAL = 2.0
_TRANSIENT_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})
_SNAPSHOT_TRANSIENT_RETRIES = 3


class Experiment(metaclass=TrackCallsMeta):
    """A LitLogger experiment run in a teamspace.

    Fetch the metrics your run has logged, or follow them live::

        exp = Experiment("run-42", teamspace="my-team")
        for row in exp.metrics(follow=True):
            print(row)

    Each row has ``_step``, ``_walltime`` and the metrics logged at that step.
    """

    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
    ) -> None:
        """Fetch an existing experiment (LitLogger metrics stream).

        Args:
            name: The experiment/run name (``name=`` passed to ``LitLogger``).
            teamspace: The teamspace the experiment lives in. Accepts a
                ``Teamspace`` instance or an ``"owner/name"`` string.
            org: Owning organisation. Deprecated — pass ``teamspace="owner/name"``.
            user: Owning user. Deprecated — pass ``teamspace="owner/name"``.

        Raises:
            ValueError: If the teamspace cannot be resolved or no experiment
                with ``name`` exists in the teamspace.
        """
        resolved_teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        if resolved_teamspace is None:
            raise ValueError(
                "Cannot resolve the teamspace from provided arguments."
                f" Got teamspace={teamspace}, org={org}, user={user}."
            )
        self._teamspace = resolved_teamspace
        self._name = name
        self._api = LitLoggerApi()
        self._stream = self._resolve_stream()

    @property
    def name(self) -> str:
        return self._name

    @property
    def teamspace(self) -> "Teamspace":
        return self._teamspace

    @property
    def id(self) -> str:
        """The underlying metrics stream ID."""
        return self._stream.id

    def metrics(
        self,
        *,
        follow: bool = False,
        tail: Optional[int] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        metric: Optional[Iterable[str]] = None,
        samples: Optional[int] = None,
    ) -> Union[List[Dict[str, Any]], Iterator[Dict[str, Any]]]:
        """Return the metrics the experiment has logged so far.

        - ``follow``: Yield the snapshot then new rows as they arrive; stop with Ctrl-C.
        - ``tail``: Only include the last N snapshot rows. Not allowed with ``follow``.
        - ``since`` / ``until``: Include only rows within this walltime range (inclusive).
        - ``metric``: Only include these metric names.
        - ``samples``: Server-side downsample target for large runs.
        """
        if follow and tail is not None:
            raise ValueError("tail cannot be combined with follow.")

        metric_filter = set(metric) if metric else None
        snapshot = self._fetch_rows(metric_filter=metric_filter, samples=samples)
        snapshot = _apply_walltime_window(snapshot, since=since, until=until)
        if tail is not None:
            snapshot = snapshot[-tail:]

        if not follow:
            return snapshot
        return self._follow(snapshot, metric_filter=metric_filter, samples=samples, since=since, until=until)

    def _resolve_stream(self) -> V1MetricsStream:
        matches = [s for s in self._api.list_metrics_streams(self._teamspace.id) if s.name == self._name]
        if not matches:
            raise ValueError(f"No experiment named '{self._name}' in teamspace '{self._teamspace.name}'.")
        return max(matches, key=lambda s: (s.updated_at or s.created_at or datetime.min))

    def _fetch_page(self, *, samples: Optional[int], transient_retries: int) -> Any:
        """Call ``get_logger_metrics``; retry up to ``transient_retries`` times on 5xx."""
        for attempt in range(transient_retries + 1):
            try:
                return self._api.get_logger_metrics(self._teamspace.id, [self._stream.id], samples=samples)
            except ApiException as ex:
                if ex.status not in _TRANSIENT_HTTP_STATUSES or attempt == transient_retries:
                    raise
                time.sleep(_FOLLOW_POLL_INTERVAL)
        raise AssertionError("unreachable")  # pragma: no cover

    def _fetch_rows(self, *, metric_filter: Optional[set], samples: Optional[int]) -> List[Dict[str, Any]]:
        response = self._fetch_page(samples=samples, transient_retries=_SNAPSHOT_TRANSIENT_RETRIES)
        return _group_by_step(response, self._stream, metric_filter=metric_filter)

    def _follow(
        self,
        snapshot: List[Dict[str, Any]],
        *,
        metric_filter: Optional[set],
        samples: Optional[int],
        since: Optional[datetime],
        until: Optional[datetime],
    ) -> Iterator[Dict[str, Any]]:
        yield from snapshot
        cursor: Optional[Tuple[datetime, int]] = (
            (snapshot[-1]["_walltime"], _step_int(snapshot[-1]["_step"])) if snapshot else None
        )
        while True:
            try:
                response = self._fetch_page(samples=samples, transient_retries=0)
            except ApiException as ex:
                if ex.status in _TRANSIENT_HTTP_STATUSES:
                    time.sleep(_FOLLOW_POLL_INTERVAL)
                    continue
                raise
            rows = _group_by_step(response, self._stream, metric_filter=metric_filter)
            for row in rows:
                walltime = row["_walltime"]
                if walltime is None:
                    continue
                if since is not None and walltime < since:
                    continue
                if until is not None and walltime > until:
                    continue
                row_key = (walltime, _step_int(row["_step"]))
                if cursor is not None and row_key <= cursor:
                    continue
                yield row
                cursor = row_key
            time.sleep(_FOLLOW_POLL_INTERVAL)


def _apply_walltime_window(
    rows: List[Dict[str, Any]], *, since: Optional[datetime], until: Optional[datetime]
) -> List[Dict[str, Any]]:
    """Client-side ``since`` / ``until`` filter; both bounds are inclusive."""
    if since is None and until is None:
        return rows
    result: List[Dict[str, Any]] = []
    for row in rows:
        walltime = row["_walltime"]
        if walltime is None:
            continue
        if since is not None and walltime < since:
            continue
        if until is not None and walltime > until:
            continue
        result.append(row)
    return result


def _group_by_step(response: Any, stream: V1MetricsStream, *, metric_filter: Optional[set]) -> List[Dict[str, Any]]:
    """Collapse the nested response into one row per step, ordered by walltime.

    When the same metric is logged twice at the same step the latest walltime wins.
    """
    named = response.named_metrics or {}
    rows: Dict[str, Dict[str, Any]] = {}

    for metric_name, per_stream in named.items():
        if metric_filter is not None and metric_name not in metric_filter:
            continue
        ids_metrics = (per_stream.ids_metrics or {}) if per_stream else {}
        entry = ids_metrics.get(stream.id)
        if entry is None or not entry.metrics_values:
            continue
        for point in entry.metrics_values:
            step = point.step
            row = rows.get(step)
            if row is None:
                row = {"_step": step, "_walltime": point.walltime, "_stream": stream.name or stream.id}
                rows[step] = row
            if point.walltime and (row["_walltime"] is None or point.walltime > row["_walltime"]):
                row["_walltime"] = point.walltime
            row[metric_name] = point.value

    return sorted(rows.values(), key=lambda r: (r["_walltime"] or datetime.min, _step_int(r["_step"])))


def _step_int(step: str) -> int:
    """Steps come over the wire as strings; sort and cursor them as ints so ``"10" > "2"``."""
    try:
        return int(step)
    except (TypeError, ValueError):
        return -1
