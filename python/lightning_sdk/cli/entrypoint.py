"""New Lightning CLI entrypoint with organized command groups."""

import os
import sys
from contextlib import suppress
from typing import Optional

import requests
import rich_click as click

from lightning_sdk import __version__
from lightning_sdk.api.studio_api import _cloud_url
from lightning_sdk.cli import groups as cli_groups
from lightning_sdk.cli.completion import completion

# Import legacy groups directly from groups.py
from lightning_sdk.cli.groups import (
    api,
    auth,
    base_studio,
    code,
    config,
    connection,
    container,
    cp,
    dataset,
    deployment,
    edit,
    file,
    folder,
    job,
    machine,
    mmt,
    model,
    pipeline,
    sandbox,
    ssh,
    studio,
    teamspace,
    user,
    vm,
)
from lightning_sdk.cli.legacy_redirects import (
    build_hidden_alias_group,
    build_legacy_forward_command,
    build_legacy_forward_group,
)
from lightning_sdk.cli.lockdown import apply_lockdown
from lightning_sdk.cli.ls import ls
from lightning_sdk.cli.rm import rm
from lightning_sdk.cli.utils.auth import browser_authentication
from lightning_sdk.cli.utils.logging import CommandLoggingGroup, logging_excepthook
from lightning_sdk.lightning_cloud import cli_login
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.utils.resolve import _get_authed_user, in_studio

click.rich_click.COMMAND_GROUPS = {
    "lightning": [
        {"name": "GET STARTED", "commands": ["login", "logout", "config", "completion"]},
        {"name": "COMPUTE", "commands": ["studio", "base-studio", "machine", "vm", "container", "sandbox"]},
        {"name": "TRAIN & DEPLOY", "commands": ["job", "mmt", "model", "deployment", "pipeline"]},
        {"name": "ACCESS", "commands": ["user", "teamspace", "auth", "ssh", "license"]},
        {"name": "DATA & FILES", "commands": ["cp", "ls", "rm", "edit", "connection"]},
        {"name": "CODING", "commands": ["code"]},
    ]
}
click.rich_click.STYLE_COMMANDS_TABLE_COLUMN_WIDTH_RATIO = (1, 3)
click.rich_click.STYLE_COMMANDS_PANEL_TITLE_STYLE = "bold #5e5e6e"
click.rich_click.STYLE_COMMANDS_PANEL_BORDER = "#2a2a38"
click.rich_click.STYLE_OPTIONS_PANEL_TITLE_STYLE = "bold #5e5e6e"
click.rich_click.STYLE_OPTIONS_PANEL_BORDER = "#2a2a38"
click.rich_click.STYLE_COMMAND = "bold #a78bfa"
click.rich_click.STYLE_USAGE = "#7a7a88"
click.rich_click.STYLE_USAGE_COMMAND = "bold #a78bfa"
click.rich_click.STYLE_ARGUMENT = "#6a6a78"
click.rich_click.STYLE_METAVAR = "dim #6FB3E8"
click.rich_click.STYLE_METAVAR_SEPARATOR = "#55555E"
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.FOOTER_TEXT = (
    "DOCS  [link=https://lightning.ai/docs/cli][#5b8cfa]https://lightning.ai/docs/cli[/#5b8cfa][/link]"
)


click.rich_click.HEADER_TEXT = (
    "[bold #a78bfa]⚡[/bold #a78bfa]  [bold #ededf2]Lightning AI[/bold #ededf2]"
    "  [#8f8f9c]The training and experimentation cloud.[/#8f8f9c]"
)


@click.group(
    name="lightning",
    cls=CommandLoggingGroup,
)
@click.version_option(__version__, message="Lightning CLI version %(version)s")
@click.pass_context
def main_cli(ctx: click.Context) -> None:
    """The AI development cloud — build, train, and ship from anywhere."""
    sys.excepthook = logging_excepthook
    ctx.with_resource(browser_authentication(False))


@main_cli.command
@click.option(
    "--no-browser",
    is_flag=True,
    help="Sign in without a browser on this machine: approve on another device, then paste the code it shows.",
)
@click.option(
    "--org",
    "orgs",
    metavar="A,B",
    help="Comma-separated organizations to ask for when the login is approved.",
)
@click.option("--project", help="Teamspace to ask for when the login is approved.")
@click.option(
    "--insecure-storage",
    is_flag=True,
    help="Store the login in a file only you can read when no OS keychain is available.",
)
def login(no_browser: bool, orgs: Optional[str], project: Optional[str], insecure_storage: bool) -> None:
    """Sign in to Lightning AI."""
    auth = Auth()
    if auth.api_key or auth.auth_token:
        click.echo('"lightning login" is not required within a Studio or when credentials are set in the environment')
        return

    if in_studio():
        # this is unexpected, as we automatically auth within a Studio
        raise RuntimeError("Unable to login within a Studio. Did you change your shell setup?") from None

    org_list = [org.strip() for org in orgs.split(",") if org.strip()] if orgs else None
    try:
        cli_login.login(
            no_browser=no_browser,
            insecure_storage=insecure_storage,
            orgs=org_list,
            project=project,
        )
    except cli_login.LoginError:
        raise
    except ConnectionError:
        raise RuntimeError(f"Unable to connect to {_cloud_url()}. Please check your internet connection.") from None

    try:
        click.echo(f'Successfully logged in as "{_get_authed_user().name}".')
    except Exception:
        # credentials are saved; only the lookup of the user's name failed
        click.echo("Successfully logged in.")


def _saved_session_token() -> Optional[str]:
    """A `sess_` token saved by an older SDK, so logout can revoke it too."""
    auth = Auth()
    try:
        if auth.load() and isinstance(auth.auth_token, str) and auth.auth_token.startswith("sess_"):
            return auth.auth_token
    except Exception:
        pass
    return None


@main_cli.command
def logout() -> None:
    """Sign out of the current session."""
    legacy = _saved_session_token()
    try:
        cli_login.logout()
    except Exception as e:
        raise RuntimeError(f"Logout failed: {e}") from e
    if legacy:
        with suppress(requests.RequestException):
            requests.post(
                f"{_cloud_url().rstrip('/')}/v1/auth/logout",
                headers={"Authorization": f"Bearer {legacy}"},
                timeout=10,
            )
    click.echo("Successfully logged out.")


# Add new command groups
main_cli.add_command(config)
main_cli.add_command(completion)
main_cli.add_command(job)
main_cli.add_command(mmt)
main_cli.add_command(machine)
main_cli.add_command(api)
main_cli.add_command(deployment)
main_cli.add_command(vm)
main_cli.add_command(container)
main_cli.add_command(model)
main_cli.add_command(pipeline)
main_cli.add_command(auth)
main_cli.add_command(code)
main_cli.add_command(file)
main_cli.add_command(folder)
main_cli.add_command(ssh)
main_cli.add_command(studio)
main_cli.add_command(user)
main_cli.add_command(teamspace)
main_cli.add_command(sandbox)
main_cli.add_command(base_studio)
main_cli.add_command(dataset)
main_cli.add_command(connection)
main_cli.add_command(cli_groups.license)
main_cli.add_command(cp)
main_cli.add_command(edit)
main_cli.add_command(ls)
main_cli.add_command(rm)

# Before the legacy forwards below, which hold references to these commands.
apply_lockdown(main_cli)

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
main_cli.add_command(build_hidden_alias_group("datasets", dataset))
main_cli.add_command(build_hidden_alias_group("studios", studio))
main_cli.add_command(build_hidden_alias_group("teamspaces", teamspace))
main_cli.add_command(build_hidden_alias_group("sandboxes", sandbox))
main_cli.add_command(build_hidden_alias_group("base-studios", base_studio))

if os.environ.get("LIGHTNING_EXPERIMENTAL_CLI_ONLY", "0") != "1":
    #### LEGACY COMMANDS ####
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
                "dataset": ("lightning dataset download", dataset.commands["download"]),
                "file": ("lightning cp", main_cli.commands["cp"]),
                "folder": ("lightning cp -r", main_cli.commands["cp"]),
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
                "file": ("lightning cp", main_cli.commands["cp"]),
                "folder": ("lightning cp -r", main_cli.commands["cp"]),
                "model": ("lightning model upload", model.commands["upload"]),
            },
        )
    )


if __name__ == "__main__":
    main_cli()
