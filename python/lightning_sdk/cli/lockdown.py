"""CLI commands that are temporarily unavailable while the API lockdown is on."""

import os

import rich_click as click

from lightning_sdk.cli.utils.unavailable import mark_temporarily_unavailable, mark_unavailable_groups
from lightning_sdk.lightning_cloud import env

# Unset, empty or truthy keeps the commands in UNAVAILABLE_COMMANDS unavailable. A false value such as 0 runs them.
LOCKDOWN_ENV = "LIGHTNING_CLI_DISABLE_UNAVAILABLE_CMDS"

UNAVAILABLE_COMMANDS: tuple[str, ...] = (
    "api deploy",
    "auth role",
    "auth roles",
    "auth whoami",
    "base-studio list",
    "code remove",
    "code setup",
    "code status",
    "config set studio",
    "config set teamspace",
    "config set user",
    "connection credentials",
    "container delete",
    "container download",
    "container list",
    "container upload",
    "cp",
    "dataset download",
    "dataset upload",
    "deployment create",
    "deployment delete",
    "deployment env delete",
    "deployment env list",
    "deployment env set",
    "deployment inspect",
    "deployment list",
    "deployment logs download",
    "deployment reload-weights",
    "deployment secret delete",
    "deployment secret list",
    "deployment secret set",
    "deployment update",
    "edit",
    "file download",
    "file upload",
    "folder download",
    "folder upload",
    "job delete",
    "job inspect",
    "job list",
    "job logs download",
    "job rename",
    "job run",
    "job ssh",
    "job stop",
    "job tag",
    "job untag",
    "license download",
    "license download-all",
    "mmt delete",
    "mmt inspect",
    "mmt list",
    "mmt logs download",
    "mmt run",
    "mmt ssh",
    "mmt stop",
    "model download",
    "model upload",
    "pipeline logs download",
    "rm",
    "sandbox command",
    "sandbox commands",
    "sandbox connect",
    "sandbox create",
    "sandbox delete",
    "sandbox list",
    "sandbox logs",
    "sandbox run",
    "sandbox snapshot create",
    "sandbox snapshot delete",
    "sandbox snapshot get",
    "sandbox snapshot list",
    "sandbox start",
    "sandbox stop",
    "sandbox update",
    "ssh configure",
    "ssh generate",
    "studio connect",
    "studio cp",
    "studio create",
    "studio delete",
    "studio env delete",
    "studio env list",
    "studio env set",
    "studio list",
    "studio ls",
    "studio open",
    "studio rm",
    "studio ssh",
    "studio start",
    "studio stop",
    "studio switch",
    "teamspace secret delete",
    "teamspace secret list",
    "teamspace secret set",
    "user secret delete",
    "user secret list",
    "user secret set",
    "vm create",
    "vm delete",
    "vm inspect",
    "vm list",
    "vm ssh",
)


def apply_lockdown(root: click.Group) -> None:
    """Replace each command in ``UNAVAILABLE_COMMANDS`` under ``root`` with a marked copy.

    Groups whose commands are all unavailable also get a notice in their help.

    Call this after the commands are registered and before anything else takes a reference
    to them, such as the legacy forwards in the entrypoint, so those forwards are marked too.

    Does nothing when ``LIGHTNING_CLI_DISABLE_UNAVAILABLE_CMDS`` is set to a false value such as ``0``,
    so every command runs as usual. The commands stay unavailable by default.

    Raises:
        KeyError: If a listed path does not name a command under ``root``.
    """
    if not env.truthy(os.getenv(LOCKDOWN_ENV) or "1"):
        return
    for path in UNAVAILABLE_COMMANDS:
        *parents, name = path.split()
        group: click.Group = root
        for parent in parents:
            group = group.commands[parent]  # type: ignore[assignment]
        group.commands[name] = mark_temporarily_unavailable(group.commands[name])
    mark_unavailable_groups(root)
