"""Deployment logs command."""

import json
import threading
import time
from contextlib import suppress
from typing import Any, Iterable, List, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
import rich_click as click

from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.cli.deployment.common import resolve_deployment, resolve_teamspace
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import V1Job

_LIVE_FALLBACK_IDLE_TIMEOUT = 8
_LIVE_FALLBACK_TAIL = 100


@click.command("logs", cls=LightningCommand)
@click.argument("name")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option("--job-id", "job_ids", multiple=True, help="Specific deployment job ID. Can be repeated.")
@click.option("--since", help="Only include logs after this timestamp.")
@click.option("--until", help="Only include logs before this timestamp.")
@click.option("--rank", type=int, help="Distributed job rank.")
@click.option("--follow", "-f", is_flag=True, default=False, help="Follow live logs after printing available pages.")
@click.option("--tail", type=int, help="Number of recent live log lines to show when following.")
def deployment_logs(
    name: str,
    teamspace: Optional[str] = None,
    job_ids: Sequence[str] = (),
    since: Optional[str] = None,
    until: Optional[str] = None,
    rank: Optional[int] = None,
    follow: bool = False,
    tail: Optional[int] = None,
) -> None:
    """Print deployment logs."""
    resolved_teamspace = resolve_teamspace(teamspace)
    api = DeploymentApi()
    deployment = resolve_deployment(api, resolved_teamspace.id, name)
    jobs = _resolve_jobs(api, resolved_teamspace.id, deployment.id, job_ids)
    if not jobs:
        click.echo("No jobs found for this deployment.")
        return

    auth_header = Auth().authenticate()
    session = requests.Session()
    session.headers.update({"Authorization": auth_header})

    follow_targets = []
    live_fallback_targets = []
    prefix = len(jobs) > 1
    for job in jobs:
        logs = api.get_job_logs(
            resolved_teamspace.id,
            job.id,
            deployment_id=deployment.id,
            since=since,
            until=until,
            rank=rank,
        )
        printed_lines = _print_pages(session, job, logs.pages or [], prefix=prefix)
        if follow:
            follow_targets.append((job, logs.follow_url))
        elif printed_lines == 0:
            live_fallback_targets.append((job, logs.follow_url))

    if follow:
        _stream_jobs(
            resolved_teamspace.id,
            follow_targets,
            auth_header,
            follow=True,
            idle_timeout=None,
            rank=rank,
            tail=tail,
            prefix=prefix,
        )
    elif live_fallback_targets:
        _stream_jobs(
            resolved_teamspace.id,
            live_fallback_targets,
            auth_header,
            follow=True,
            idle_timeout=_LIVE_FALLBACK_IDLE_TIMEOUT,
            rank=rank,
            tail=tail or _LIVE_FALLBACK_TAIL,
            prefix=prefix,
        )


def _resolve_jobs(
    api: DeploymentApi,
    teamspace_id: str,
    deployment_id: str,
    job_ids: Sequence[str],
) -> List[V1Job]:
    if job_ids:
        all_jobs = api.list_deployment_jobs(teamspace_id, deployment_id, limit=100)
        jobs_by_id = {job.id: job for job in all_jobs}
        return [
            jobs_by_id.get(job_id) or V1Job(id=job_id, name=job_id, deployment_id=deployment_id) for job_id in job_ids
        ]
    return api.list_deployment_jobs(teamspace_id, deployment_id, limit=100)


def _print_pages(session: requests.Session, job: V1Job, pages: Iterable[Any], *, prefix: bool) -> int:
    lines = 0
    for page in pages:
        url = getattr(page, "url", None)
        if not url:
            continue
        response = session.get(_absolute_url(url), timeout=60)
        response.raise_for_status()
        lines += _print_page_text(job, response.text, prefix=prefix)
    return lines


def _print_page_text(job: V1Job, text: str, *, prefix: bool) -> int:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        lines = 0
        for line in text.splitlines():
            _echo_log_line(job, line, prefix=prefix)
            lines += 1
        return lines

    entries = payload if isinstance(payload, list) else [payload]
    lines = 0
    for entry in entries:
        if isinstance(entry, dict):
            _echo_log_line(job, entry.get("message") or entry.get("Message") or json.dumps(entry), prefix=prefix)
        else:
            _echo_log_line(job, str(entry), prefix=prefix)
        lines += 1
    return lines


def _stream_jobs(
    teamspace_id: str,
    jobs: Sequence[tuple[V1Job, Optional[str]]],
    auth_header: str,
    *,
    follow: bool,
    idle_timeout: Optional[float],
    rank: Optional[int],
    tail: Optional[int],
    prefix: bool,
) -> None:
    try:
        import websocket
        from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException
    except ImportError as ex:
        raise click.ClickException("Following logs requires the websocket-client package.") from ex

    stop_event = threading.Event()
    sockets = []
    threads = []
    errors = []

    def worker(job: V1Job, follow_url: Optional[str]) -> None:
        url = _follow_url(follow_url, teamspace_id, job.id, follow=follow, rank=rank, tail=tail)
        while not stop_event.is_set():
            ws = None
            kwargs = {"header": [f"Authorization: {auth_header}"]}
            if idle_timeout is not None:
                kwargs["timeout"] = idle_timeout
            try:
                ws = websocket.create_connection(_websocket_url(url), **kwargs)
                sockets.append(ws)
                while not stop_event.is_set():
                    try:
                        message = ws.recv()
                    except WebSocketTimeoutException:
                        if idle_timeout is not None:
                            stop_event.set()
                            break
                        raise
                    except WebSocketConnectionClosedException:
                        if idle_timeout is not None:
                            stop_event.set()
                        break
                    _print_websocket_message(job, message, prefix=prefix)
                if idle_timeout is not None:
                    break
            except WebSocketConnectionClosedException:
                if idle_timeout is not None:
                    stop_event.set()
                    break
            except Exception as ex:
                if not stop_event.is_set():
                    errors.append(ex)
                    stop_event.set()
            finally:
                if ws is not None:
                    with suppress(Exception):
                        ws.close()

            if follow and not stop_event.is_set():
                time.sleep(1)

    for job, follow_url in jobs:
        thread = threading.Thread(target=worker, args=(job, follow_url), daemon=True)
        thread.start()
        threads.append(thread)

    try:
        while any(thread.is_alive() for thread in threads):
            if errors:
                for ws in sockets:
                    ws.close()
            for thread in threads:
                thread.join(timeout=0.2)
    except KeyboardInterrupt:
        stop_event.set()
        for ws in sockets:
            ws.close()
    if errors:
        raise click.ClickException(str(errors[0]))


def _print_websocket_message(job: V1Job, message: str, *, prefix: bool) -> None:
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        _echo_log_line(job, message, prefix=prefix)
        return

    entries = payload if isinstance(payload, list) else [payload]
    for entry in entries:
        if isinstance(entry, dict):
            _echo_log_line(job, entry.get("message") or entry.get("Message") or json.dumps(entry), prefix=prefix)
        else:
            _echo_log_line(job, str(entry), prefix=prefix)


def _echo_log_line(job: V1Job, line: str, *, prefix: bool) -> None:
    if prefix:
        click.echo(f"[{job.name or job.id}] {line}")
    else:
        click.echo(line)


def _absolute_url(url: str) -> str:
    if url.startswith(("http://", "https://", "ws://", "wss://")):
        return url
    return f"{_get_cloud_url().rstrip('/')}/{url.lstrip('/')}"


def _websocket_url(url: str) -> str:
    absolute = _absolute_url(url)
    if absolute.startswith("https://"):
        return "wss://" + absolute[len("https://") :]
    if absolute.startswith("http://"):
        return "ws://" + absolute[len("http://") :]
    return absolute


def _follow_url(
    follow_url: Optional[str],
    teamspace_id: str,
    job_id: str,
    *,
    follow: bool,
    rank: Optional[int],
    tail: Optional[int],
) -> str:
    url = follow_url or f"/v1/projects/{teamspace_id}/jobs/{job_id}/logs"
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({"follow": str(follow).lower(), "direction": "forward"})
    if rank is not None:
        query["rank"] = str(rank)
    if tail is not None:
        query["tail"] = str(tail)
    return urlunparse(parsed._replace(query=urlencode(query)))
