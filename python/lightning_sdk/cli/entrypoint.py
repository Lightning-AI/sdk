"""New Lightning CLI entrypoint with organized command groups."""

import os
import sys

import click

from lightning_sdk import __version__
from lightning_sdk.api.studio_api import _cloud_url

# Import legacy groups directly from groups.py
from lightning_sdk.cli.groups import (
    api,
    api_key,
    base_studio,
    config,
    container,
    cp,
    deployment,
    file,
    folder,
    job,
    license,
    machine,
    mmt,
    model,
    ssh,
    studio,
    vm,
)
from lightning_sdk.cli.legacy_redirects import (
    build_hidden_alias_group,
    build_legacy_forward_command,
    build_legacy_forward_group,
)
from lightning_sdk.cli.utils import CustomHelpFormatter
from lightning_sdk.cli.utils.logging import CommandLoggingGroup, logging_excepthook
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.utils.resolve import _get_authed_user, in_studio


@click.group(
    name="lightning",
    help="Command line interface (CLI) to interact with/manage Lightning AI Studios.",
    cls=CommandLoggingGroup,
)
@click.version_option(__version__, message="Lightning CLI version %(version)s")
def main_cli() -> None:
    sys.excepthook = logging_excepthook


main_cli.context_class.formatter_class = CustomHelpFormatter


@main_cli.command
def login() -> None:
    """Login to Lightning AI Studios."""
    # try to fetch credentials, if successful (e.g. in a Studio or already logged in), no need to relogin
    auth = Auth()
    if (auth.user_id and auth.api_key) or auth.load():
        try:
            auth_user = _get_authed_user()
            click.echo(f'You are currently logged in as "{auth_user.name}"')
        except Exception:
            click.echo("You are already logged in")
        click.echo('"lightning login" is not required within a Studio or when already logged in')
        return

    if in_studio():
        # this is unexpected, as we automatically auth within a Studio
        raise RuntimeError("Unable to login within a Studio. Did you change your shell setup?") from None

    auth.clear()
    try:
        auth.authenticate()
    except ConnectionError:
        raise RuntimeError(f"Unable to connect to {_cloud_url()}. Please check your internet connection.") from None


@main_cli.command
def logout() -> None:
    """Logout from Lightning AI Studios."""
    auth = Auth()
    auth.clear()


# Add new command groups
main_cli.add_command(config)
main_cli.add_command(job)
main_cli.add_command(mmt)
main_cli.add_command(machine)
main_cli.add_command(api)
main_cli.add_command(deployment)
main_cli.add_command(container)
main_cli.add_command(model)
main_cli.add_command(api_key)
main_cli.add_command(file)
main_cli.add_command(folder)
main_cli.add_command(ssh)
main_cli.add_command(studio)
main_cli.add_command(vm)
main_cli.add_command(base_studio)
main_cli.add_command(license)
main_cli.add_command(cp)

# hidden plural aliases for noun-first groups
main_cli.add_command(build_hidden_alias_group("apis", api))
main_cli.add_command(build_hidden_alias_group("jobs", job))
main_cli.add_command(build_hidden_alias_group("mmts", mmt))
main_cli.add_command(build_hidden_alias_group("machines", machine))
main_cli.add_command(build_hidden_alias_group("deployments", deployment))
main_cli.add_command(build_hidden_alias_group("containers", container))
main_cli.add_command(build_hidden_alias_group("models", model))
main_cli.add_command(build_hidden_alias_group("files", file))
main_cli.add_command(build_hidden_alias_group("folders", folder))
main_cli.add_command(build_hidden_alias_group("studios", studio))
main_cli.add_command(build_hidden_alias_group("vms", vm))
main_cli.add_command(build_hidden_alias_group("base-studios", base_studio))

if os.environ.get("LIGHTNING_EXPERIMENTAL_CLI_ONLY", "0") != "1":
    #### LEGACY COMMANDS ####
    from lightning_sdk.cli.legacy.ai_hub import aihub

    main_cli.add_command(aihub)
    main_cli.add_command(
        build_legacy_forward_group("configure", {"ssh": ("lightning ssh configure", ssh.commands["configure"])})
    )
    main_cli.add_command(
        build_legacy_forward_group("connect", {"studio": ("lightning studio ssh", studio.commands["ssh"])})
    )
    main_cli.add_command(
        build_legacy_forward_group("create", {"studio": ("lightning studio create", studio.commands["create"])})
    )
    main_cli.add_command(
        build_legacy_forward_group(
            "delete",
            {
                "container": ("lightning container delete", container.commands["delete"]),
                "job": ("lightning job delete", job.commands["delete"]),
                "mmt": ("lightning mmt delete", mmt.commands["delete"]),
                "studio": ("lightning studio delete", studio.commands["delete"]),
            },
        )
    )
    main_cli.add_command(
        build_legacy_forward_group("deploy", {"api": ("lightning api deploy", api.commands["deploy"])})
    )
    main_cli.add_command(
        build_legacy_forward_group("dockerize", {"api": ("lightning api dockerize", api.commands["dockerize"])})
    )
    main_cli.add_command(
        build_legacy_forward_group(
            "download",
            {
                "container": ("lightning container download", container.commands["download"]),
                "file": ("lightning file download", file.commands["download"]),
                "folder": ("lightning folder download", folder.commands["download"]),
                "model": ("lightning model download", model.commands["download"]),
            },
        )
    )
    main_cli.add_command(
        build_legacy_forward_group("generate", {"ssh": ("lightning ssh generate", ssh.commands["generate"])})
    )
    main_cli.add_command(
        build_legacy_forward_group(
            "inspect",
            {
                "job": ("lightning job inspect", job.commands["inspect"]),
                "mmt": ("lightning mmt inspect", mmt.commands["inspect"]),
            },
        )
    )
    main_cli.add_command(
        build_legacy_forward_group(
            "list",
            {
                "containers": ("lightning container list", container.commands["list"]),
                "jobs": ("lightning job list", job.commands["list"]),
                "machines": ("lightning machine list", machine.commands["list"]),
                "mmts": ("lightning mmt list", mmt.commands["list"]),
                "studios": ("lightning studio list", studio.commands["list"]),
            },
        )
    )
    main_cli.add_command(build_legacy_forward_command("open", "lightning studio open", studio.commands["open"]))
    main_cli.add_command(
        build_legacy_forward_group(
            "run",
            {
                "job": ("lightning job run", job.commands["run"]),
                "mmt": ("lightning mmt run", mmt.commands["run"]),
            },
        )
    )
    main_cli.add_command(
        build_legacy_forward_group("start", {"studio": ("lightning studio start", studio.commands["start"])})
    )
    main_cli.add_command(
        build_legacy_forward_group(
            "stop",
            {
                "job": ("lightning job stop", job.commands["stop"]),
                "mmt": ("lightning mmt stop", mmt.commands["stop"]),
                "studio": ("lightning studio stop", studio.commands["stop"]),
            },
        )
    )
    main_cli.add_command(
        build_legacy_forward_group("switch", {"studio": ("lightning studio switch", studio.commands["switch"])})
    )
    main_cli.add_command(
        build_legacy_forward_group(
            "upload",
            {
                "container": ("lightning container upload", container.commands["upload"]),
                "file": ("lightning file upload", file.commands["upload"]),
                "folder": ("lightning folder upload", folder.commands["upload"]),
                "model": ("lightning model upload", model.commands["upload"]),
            },
        )
    )


if __name__ == "__main__":
    main_cli()
