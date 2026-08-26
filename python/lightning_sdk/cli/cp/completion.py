"""Shell completion for local and remote ``cp`` paths."""

import posixpath
from typing import Any, Iterable

import rich_click as click
from click.shell_completion import (
    BashComplete,
    CompletionItem,
    ZshComplete,
    add_completion_class,
)

from lightning_sdk.api.filesystem_api import FilesystemApi
from lightning_sdk.cli.resource_completion import accessible_teamspaces as _accessible_teamspaces
from lightning_sdk.cli.resource_completion import has_credentials as _has_credentials

_LIT_PREFIX = "lit://"

_BASH_SOURCE = BashComplete.source_template.replace(
    """        elif [[ $type == 'plain' ]]; then
            COMPREPLY+=($value)""",
    """        elif [[ $type == 'plain' ]]; then
            COMPREPLY+=($value)
            if [[ $value == */ ]]; then
                compopt -o nospace
            fi""",
)

_ZSH_SOURCE = (
    ZshComplete.source_template.replace(
        "    local -a response",
        """    local -a remote_directories
    local -a response""",
    )
    .replace(
        '            if [[ "$descr" == "_" ]]; then',
        """            if [[ "$key" == */ ]]; then
                remote_directories+=("$key")
            elif [[ "$descr" == "_" ]]; then""",
    )
    .replace(
        '    if [ -n "$completions" ]; then\n        compadd -U -V unsorted -a completions\n    fi',
        """    if [ -n "$completions" ]; then
        compadd -U -V unsorted -a completions
    fi

    if [ -n "$remote_directories" ]; then
        compadd -S '' -U -V unsorted -a remote_directories
    fi""",
    )
)


class _LightningBashComplete(BashComplete):
    source_template = _BASH_SOURCE


class _LightningZshComplete(ZshComplete):
    source_template = _ZSH_SOURCE


add_completion_class(_LightningBashComplete, name="bash")
add_completion_class(_LightningZshComplete, name="zsh")


def complete_cp_path(
    _ctx: click.Context,
    _param: click.Parameter,
    incomplete: str,
) -> list[CompletionItem]:
    """Complete local paths through the shell and ``lit://`` paths through the API."""
    if not incomplete.startswith(_LIT_PREFIX):
        return [CompletionItem(incomplete, type="file")]
    return _safe_remote_completions(incomplete)


def complete_remote_path(
    _ctx: click.Context,
    _param: click.Parameter,
    incomplete: str,
) -> list[CompletionItem]:
    """Complete ``lit://`` paths only, for commands whose argument is always remote."""
    if not incomplete.startswith(_LIT_PREFIX):
        # Steer the shell toward lit:// instead of offering local files.
        return [CompletionItem(_LIT_PREFIX)] if _LIT_PREFIX.startswith(incomplete) else []
    return _safe_remote_completions(incomplete)


def _safe_remote_completions(incomplete: str) -> list[CompletionItem]:
    try:
        if not _has_credentials():
            return []
        return _complete_remote_path(incomplete)
    except Exception:
        # Shell completion must never turn a missing login, an unavailable API,
        # or a stale remote path into an interactive prompt or a traceback.
        return []


def _complete_remote_path(incomplete: str) -> list[CompletionItem]:
    parts = incomplete[len(_LIT_PREFIX) :].split("/")

    if parts[0] == "" and len(parts) > 1:
        # Relative form lit:///<path> — complete from the current teamspace's drive.
        from lightning_sdk.utils.resolve import _resolve_teamspace

        teamspace = _resolve_teamspace(teamspace=None, org=None, user=None)
        if teamspace is None:
            return []
        parent = "/".join(parts[1:-1])
        entries = FilesystemApi().list_files(teamspace.id, parent, recursive=False)
        return _complete_tree_entries(incomplete, entries)

    if len(parts) == 1:
        owner_names = _accessible_teamspaces()
        return _complete_values(
            incomplete,
            (f"{_LIT_PREFIX}{owner}/" for owner in owner_names),
        ) + _complete_values(incomplete, [f"{_LIT_PREFIX}/"])

    owner = parts[0]
    if len(parts) == 2:
        teamspaces = _accessible_teamspaces().get(owner, {})
        return _complete_values(
            incomplete,
            (f"{_LIT_PREFIX}{owner}/{teamspace}/" for teamspace in teamspaces),
        )

    teamspace_id = _accessible_teamspaces().get(owner, {}).get(parts[1])
    if teamspace_id is None:
        return []

    # Anything deeper completes from the drive's own tree listing, so every
    # namespace the server serves is completable — no client-side list.
    parent = "/".join(parts[2:-1])
    entries = FilesystemApi().list_files(teamspace_id, parent, recursive=False)
    return _complete_tree_entries(incomplete, entries)


def _complete_values(
    incomplete: str,
    values: Iterable[str],
) -> list[CompletionItem]:
    return [CompletionItem(value) for value in sorted(set(values)) if value.startswith(incomplete)]


def _complete_tree_entries(incomplete: str, entries: list[dict[str, Any]]) -> list[CompletionItem]:
    partial = incomplete.rsplit("/", 1)[-1]
    base = incomplete[: -len(partial)] if partial else incomplete
    items = []

    for entry in entries:
        name = posixpath.basename(entry.get("path", "").rstrip("/"))
        if not name:
            continue
        value = f"{base}{name}{'/' if entry.get('type') == 'tree' else ''}"
        if value.startswith(incomplete):
            items.append(CompletionItem(value))

    return sorted(items, key=lambda item: item.value)
