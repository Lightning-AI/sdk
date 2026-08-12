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
from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.cli.resource_completion import accessible_teamspaces as _accessible_teamspaces
from lightning_sdk.cli.resource_completion import has_credentials as _has_credentials
from lightning_sdk.cli.resource_completion import studios as _studios

_LIT_PREFIX = "lit://"
_REMOTE_RESOURCE_TYPES = ("studios", "uploads")

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

    if len(parts) == 1:
        owner_names = _accessible_teamspaces()
        return _complete_values(incomplete, (f"{_LIT_PREFIX}{owner}/" for owner in owner_names))

    owner = parts[0]
    if len(parts) == 2:
        teamspaces = _accessible_teamspaces().get(owner, {})
        return _complete_values(
            incomplete,
            (f"{_LIT_PREFIX}{owner}/{teamspace}/" for teamspace in teamspaces),
        )

    teamspace = parts[1]
    if len(parts) == 3:
        base = f"{_LIT_PREFIX}{owner}/{teamspace}/"
        return _complete_values(
            incomplete,
            (f"{base}{resource_type}/" for resource_type in _REMOTE_RESOURCE_TYPES),
        )

    teamspace_id = _accessible_teamspaces().get(owner, {}).get(teamspace)
    if teamspace_id is None:
        return []

    resource_type = parts[2]
    if resource_type == "studios":
        return _complete_studio_path(incomplete, parts[3:], teamspace_id)
    if resource_type == "uploads":
        return _complete_uploads_path(incomplete, parts[3:], teamspace_id)
    return []


def _complete_studio_path(incomplete: str, path_parts: list[str], teamspace_id: str) -> list[CompletionItem]:
    studios = _studios(teamspace_id)
    studio_name = path_parts[0]
    if len(path_parts) == 1:
        base = incomplete[: -len(studio_name)] if studio_name else incomplete
        return _complete_values(incomplete, (f"{base}{name}/" for name in studios))

    studio_id = studios.get(studio_name)
    if studio_id is None:
        return []

    parent = "/".join(path_parts[1:-1])
    tree = StudioApi().get_tree(studio_id, teamspace_id, path=parent)
    return _complete_tree_entries(incomplete, tree.get("tree", []))


def _complete_uploads_path(incomplete: str, path_parts: list[str], teamspace_id: str) -> list[CompletionItem]:
    parent = "/".join(path_parts[:-1])
    remote_parent = posixpath.join("Uploads", parent)
    entries = FilesystemApi().list_files(teamspace_id, remote_parent, recursive=False)
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
