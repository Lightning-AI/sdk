"""Top-level `lightning logs` command."""

import json
import re
import shlex
from typing import List, Optional, Tuple

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand

_SEVERITIES = ["error", "warning", "info", "debug"]

# Lightning brand purple (#a78bfa) as an RGB tuple for truecolor styling.
_MATCH_COLOR = (167, 139, 250)


def _highlight(text: str, query: Optional[str]) -> str:
    """Wrap case-insensitive occurrences of ``query`` in ``text`` with a match style.

    click.echo strips these ANSI codes automatically when stdout is not a terminal, so
    piped/redirected output stays plain.
    """
    if not query:
        return text
    return re.sub(
        re.escape(query),
        lambda m: click.style(m.group(0), fg=_MATCH_COLOR, bold=True),
        text,
        flags=re.IGNORECASE,
    )


def _format_entry(entry: "object", timestamps: bool, query: Optional[str] = None) -> str:
    message = _highlight(getattr(entry, "message", "") or "", query)
    timestamp = getattr(entry, "timestamp", None)
    if timestamps and timestamp is not None:
        return f"{timestamp.isoformat()}  {message}"
    return message


def _exclusive(id_value: Optional[str], name_value: Optional[str], resource: str) -> None:
    if id_value and name_value:
        raise click.UsageError(f"Pass only one of --{resource}-id / --{resource}-name.")


def _next_page_command(base_flags: List[Tuple[str, str]], timestamps: bool, next_token: str) -> str:
    """Render a copy-paste command that fetches the next page with the same filters."""
    parts = ["lightning", "logs"]
    for flag, value in base_flags:
        parts += [flag, shlex.quote(str(value))]
    if not timestamps:
        parts.append("--no-timestamps")
    parts += ["--page-token", shlex.quote(next_token)]
    return " ".join(parts)


def _resolve_sandbox_id(name: str, teamspace: "object") -> str:
    from lightning_sdk.sandbox.sandbox import Sandbox

    client = Sandbox()
    page_token: Optional[str] = None
    try:
        while True:
            result = client.list(teamspace=teamspace, page_token=page_token)
            for sandbox in result.sandboxes:
                if sandbox.name == name:
                    return sandbox.sandbox_id
            page_token = result.next_page_token or None
            if not page_token:
                break
    except RuntimeError as ex:
        # Listing sandboxes hits the sandbox API, which the server gates behind a
        # teamspace/org-scoped key — a personal login key gets a 403. The logs endpoint
        # itself takes --sandbox-id directly with the normal login, so point there.
        raise click.ClickException(
            "Looking up a sandbox by name requires a teamspace- or org-scoped API key "
            "(set LIGHTNING_SANDBOX_API_KEY); a personal login key can't list sandboxes. "
            "Pass --sandbox-id instead — it works with your normal login."
        ) from ex
    raise click.ClickException(f"No sandbox named '{name}' found in {teamspace.name}. Pass --sandbox-id instead.")


@click.command("logs", cls=LightningCommand)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the teamspace to search logs in, as {owner}/{name} (e.g. my-org/my-teamspace). "
        "If not provided, can be selected interactively."
    ),
)
@click.option("--job-id", "--job_id", "job_id", default=None, help="restrict to a job (by id).")
@click.option("--job-name", "--job_name", "job_name", default=None, help="restrict to a job (by name).")
@click.option(
    "--deployment-id", "--deployment_id", "deployment_id", default=None, help="restrict to a deployment (by id)."
)
@click.option(
    "--deployment-name",
    "--deployment_name",
    "deployment_name",
    default=None,
    help="restrict to a deployment (by name).",
)
@click.option("--mmt-id", "--mmt_id", "mmt_id", default=None, help="restrict to a multi-machine job (by id).")
@click.option("--mmt-name", "--mmt_name", "mmt_name", default=None, help="restrict to a multi-machine job (by name).")
@click.option("--sandbox-id", "--sandbox_id", "sandbox_id", default=None, help="restrict to a sandbox (by id).")
@click.option("--sandbox-name", "--sandbox_name", "sandbox_name", default=None, help="restrict to a sandbox (by name).")
@click.option(
    "--sandbox-command-id",
    "--sandbox_command_id",
    "sandbox_command_id",
    default=None,
    help="restrict to a single sandbox command (by id).",
)
@click.option("--query", "-q", default=None, help="only return lines matching this text.")
@click.option(
    "--severity",
    default=None,
    type=click.Choice(_SEVERITIES, case_sensitive=False),
    help="minimum severity to include (error > warning > info > debug).",
)
@click.option("--since", default=None, help='only lines at or after this time (e.g. "1h", RFC3339).')
@click.option("--until", default=None, help="only lines at or before this time.")
@click.option("--limit", "-n", "limit", default=None, type=int, help="maximum number of lines to return.")
@click.option(
    "--page-token",
    "--page_token",
    "page_token",
    default=None,
    help="cursor from a previous run's next page token, to fetch the following page.",
)
@click.option("--timestamps/--no-timestamps", default=True, help="prefix each line with its timestamp.")
@click.option("--json", "as_json", is_flag=True, help="emit entries and the next page token as JSON.")
def logs(
    teamspace: Optional[str],
    job_id: Optional[str],
    job_name: Optional[str],
    deployment_id: Optional[str],
    deployment_name: Optional[str],
    mmt_id: Optional[str],
    mmt_name: Optional[str],
    sandbox_id: Optional[str],
    sandbox_name: Optional[str],
    sandbox_command_id: Optional[str],
    query: Optional[str],
    severity: Optional[str],
    since: Optional[str],
    until: Optional[str],
    limit: Optional[int],
    page_token: Optional[str],
    timestamps: bool,
    as_json: bool,
) -> None:
    """Search and page through logs across a teamspace.

    Filter by resource (--job-id/--job-name, --deployment-id/--deployment-name,
    --mmt-id/--mmt-name, --sandbox-id/--sandbox-name, --sandbox-command-id), text (--query),
    severity and time range. Results are paginated: re-run with --page-token set to the token
    printed at the end of the previous page to continue.

    Examples:
      lightning logs --job-name my-job --query error --limit 100
      lightning logs --deployment-name my-api --severity warning
      lightning logs --sandbox-id sbx-42 --sandbox-command-id cmd-abc
      lightning logs --job-id job-123 --page-token <token>
    """
    from lightning_sdk.api.deployment_api import DeploymentApi
    from lightning_sdk.api.job_api import JobApiV2
    from lightning_sdk.cli.legacy.job_and_mmt_action import _JobAndMMTAction

    _exclusive(job_id, job_name, "job")
    _exclusive(deployment_id, deployment_name, "deployment")
    _exclusive(mmt_id, mmt_name, "mmt")
    _exclusive(sandbox_id, sandbox_name, "sandbox")

    # Captured before resolution rewrites the *_id vars, so the reproduced next-page
    # command reflects the filters the user actually typed. --page-token is added fresh.
    base_flags: List[Tuple[str, str]] = [
        (flag, value)
        for flag, value in (
            ("--teamspace", teamspace),
            ("--job-id", job_id),
            ("--job-name", job_name),
            ("--deployment-id", deployment_id),
            ("--deployment-name", deployment_name),
            ("--mmt-id", mmt_id),
            ("--mmt-name", mmt_name),
            ("--sandbox-id", sandbox_id),
            ("--sandbox-name", sandbox_name),
            ("--sandbox-command-id", sandbox_command_id),
            ("--query", query),
            ("--severity", severity),
            ("--since", since),
            ("--until", until),
            ("--limit", str(limit) if limit is not None else None),
        )
        if value
    ]

    action = _JobAndMMTAction()
    resolved_teamspace = action(teamspace)

    job_ids: Optional[List[str]] = None
    if job_name is not None:
        job_ids = [action._resolve_job(job_name, teamspace=resolved_teamspace).resource_id]
    elif job_id is not None:
        job_ids = [job_id]

    if mmt_name is not None:
        mmt_id = action._resolve_mmt(mmt_name, teamspace=resolved_teamspace).resource_id

    if deployment_name is not None:
        deployment = DeploymentApi().get_deployment_by_name(deployment_name, resolved_teamspace.id)
        if deployment is None:
            raise click.ClickException(f"No deployment named '{deployment_name}' found in {resolved_teamspace.name}.")
        deployment_id = deployment.id

    if sandbox_name is not None:
        sandbox_id = _resolve_sandbox_id(sandbox_name, resolved_teamspace)

    response = JobApiV2().search_logs(
        teamspace_id=resolved_teamspace.id,
        job_ids=job_ids,
        deployment_id=deployment_id,
        mmt_id=mmt_id,
        sandbox_id=sandbox_id,
        sandbox_command_ids=[sandbox_command_id] if sandbox_command_id else None,
        query=query,
        severity=severity.lower() if severity else None,
        since=since,
        until=until,
        page_size=limit,
        page_token=page_token,
    )

    entries = response.entries or []
    next_page_token = response.next_page_token or None

    if as_json:
        payload = {
            "entries": [
                {
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp is not None else None,
                    "message": entry.message,
                    "severity": entry.severity,
                    "resource_id": entry.resource_id,
                    "line": entry.line,
                }
                for entry in entries
            ],
            "next_page_token": next_page_token,
            "follow_url": response.follow_url or None,
        }
        click.echo(json.dumps(payload, indent=2))
        return

    for entry in entries:
        click.echo(_format_entry(entry, timestamps, query))

    # Cursor hint goes to stderr so piping stdout (e.g. `| grep`) stays clean.
    if next_page_token:
        click.echo("\nNext page — run:", err=True)
        click.echo(f"  {_next_page_command(base_flags, timestamps, next_page_token)}", err=True)
    elif not entries:
        click.echo("No logs matched.", err=True)
