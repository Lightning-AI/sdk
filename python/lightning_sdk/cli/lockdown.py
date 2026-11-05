"""CLI commands that are temporarily unavailable while the API lockdown is on."""

import os
from collections.abc import Callable, Mapping
from typing import Any

import rich_click as click

from lightning_sdk.cli.utils import lockdown_status
from lightning_sdk.cli.utils.lockdown_status import (
    ENVIRONMENT_TEMPLATES,
    RW_FILESYSTEM,
    STUDIO_DELETE,
    STUDIO_SIDECAR_AUTH,
    STUDIO_SSH,
    STUDIO_SWITCHING,
    STUDIOS,
)
from lightning_sdk.cli.utils.unavailable import mark_temporarily_unavailable, mark_unavailable_groups
from lightning_sdk.lightning_cloud import env

# Unset, empty or truthy keeps the commands in UNAVAILABLE_COMMANDS unavailable. A false value such as 0 runs them.
LOCKDOWN_ENV = "LIGHTNING_CLI_DISABLE_UNAVAILABLE_CMDS"

# Unavailable whenever the lockdown is on. Some make no request the lockdown blocks, but the services
# they rely on don't work yet: LitCR is offline, and code.lightning.ai doesn't accept keys yet.
UNAVAILABLE_COMMANDS: tuple[str, ...] = (
    "auth role",
    "auth roles",
    "auth whoami",
    "code remove",
    "code setup",
    "code status",
    "connection credentials",
    "container delete",
    "container download",
    "container list",
    "container upload",
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
    "studio connect",
    "studio env delete",
    "studio env set",
    "studio list",
    "studio ls",
    "studio open",
    "studio rm",
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

# The capabilities each command needs, all of them. Starting and stopping need the Studio's sidecar to keep
# renewing its token, so they need studio-sidecar-auth as well as studios. Deleting needs studio-delete as
# well as studios: the config lists only the capabilities the caller holds, not their prerequisites.
GATED_COMMANDS: Mapping[str, tuple[str, ...]] = {
    "base-studio list": (ENVIRONMENT_TEMPLATES,),
    "edit": (RW_FILESYSTEM,),
    "file upload": (RW_FILESYSTEM,),
    "folder upload": (RW_FILESYSTEM,),
    "rm": (RW_FILESYSTEM,),
    "ssh configure": (STUDIO_SSH,),
    "studio create": (STUDIOS, STUDIO_SIDECAR_AUTH, ENVIRONMENT_TEMPLATES),
    "studio delete": (STUDIOS, STUDIO_DELETE),
    "studio env list": (STUDIOS, STUDIO_SIDECAR_AUTH),
    "studio ssh": (STUDIO_SSH,),
    "studio start": (STUDIOS, STUDIO_SIDECAR_AUTH),
    "studio stop": (STUDIOS, STUDIO_SIDECAR_AUTH),
    "studio switch": (STUDIO_SWITCHING,),
}


def _lockdown_on(_params: Mapping[str, Any]) -> bool:
    return lockdown_status.lockdown_on()


def _capabilities_closed(flags: tuple[str, ...]) -> Callable[[Mapping[str, Any]], bool]:
    return lambda _params: any(lockdown_status.capability_closed(capability) for capability in flags)


def _upload_closed(params: Mapping[str, Any]) -> bool:
    """Whether ``params`` are an upload while uploads are closed. A copy from a local source is an upload.

    This checks only the uploads flag. An upload to a teamspace's ``uploads/`` or ``artifacts/`` root can also
    need a cloud account: the server rejects it without a ``ClusterID``, and the CLI then lists the cloud
    accounts, which needs ``basic-site`` as well. So with uploads open but ``basic-site`` closed, that upload is
    refused by the server and shows the same notice. Uploads to a ``studios/`` folder or an R2 ``lightning_storage``
    folder don't reach that lookup.
    """
    source = params.get("source")
    uploading = isinstance(source, str) and not source.startswith("lit://")
    return uploading and lockdown_status.capability_closed(RW_FILESYSTEM)


def _deploying(params: Mapping[str, Any]) -> bool:
    """Whether ``params`` deploy to the cloud, which the lockdown never opens. Without them it serves locally."""
    return (params.get("cloud") is not None or params.get("devbox") is not None) and lockdown_status.lockdown_on()


# Unavailable only when run with some parameters: a copy is gated only when it uploads
PARAM_GATED_COMMANDS: Mapping[str, Callable[[Mapping[str, Any]], bool]] = {
    "api deploy": _deploying,
    "cp": _upload_closed,
    "studio cp": _upload_closed,
}

LOCKDOWN_COMMANDS: tuple[str, ...] = (*UNAVAILABLE_COMMANDS, *GATED_COMMANDS, *PARAM_GATED_COMMANDS)

_DETAILS: Mapping[str, str] = {
    "api deploy": "Only --cloud and --devbox are unavailable: serving locally still works.",
}


def apply_lockdown(root: click.Group) -> None:
    """Replace each command in ``LOCKDOWN_COMMANDS`` under ``root`` with a marked copy.

    Groups whose commands are all marked also get a notice in their help while they are all unavailable.

    Call this after the commands are registered and before anything else takes a reference
    to them, such as the legacy forwards in the entrypoint, so those forwards are marked too.

    Does nothing when ``LIGHTNING_CLI_DISABLE_UNAVAILABLE_CMDS`` is set to a false value such as ``0``,
    so every command runs as usual. The commands stay unavailable by default.

    Raises:
        KeyError: If a listed path does not name a command under ``root``.
    """
    if not env.truthy(os.getenv(LOCKDOWN_ENV) or "1"):
        return
    gates = {
        **{path: _lockdown_on for path in UNAVAILABLE_COMMANDS},
        **{path: _capabilities_closed(flags) for path, flags in GATED_COMMANDS.items()},
        **PARAM_GATED_COMMANDS,
    }
    for path, unavailable in gates.items():
        *parents, name = path.split()
        group: click.Group = root
        for parent in parents:
            group = group.commands[parent]  # type: ignore[assignment]
        group.commands[name] = mark_temporarily_unavailable(
            group.commands[name], _DETAILS.get(path), unavailable=unavailable
        )
    mark_unavailable_groups(root)
