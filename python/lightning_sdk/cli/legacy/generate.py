from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.legacy.studios_menu import _StudiosMenu


@click.group(name="generate")
def generate() -> None:
    """Generate configs (such as ssh for studio) and print them to commandline."""


@generate.command(name="ssh")
@click.option(
    "--name",
    default=None,
    help=(
        "The name of the studio to obtain SSH config. "
        "If not specified, tries to infer from the environment (e.g. when run from within a Studio.)"
    ),
)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace the studio is part of. "
        "Should be of format <OWNER>/<TEAMSPACE_NAME>. "
        "If not specified, tries to infer from the environment (e.g. when run from within a Studio.)"
    ),
)
def ssh(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Get SSH config entry for a studio."""
    menu = _StudiosMenu()
    studio = menu._get_studio(name=name, teamspace=teamspace)

    conf = _generate_ssh_config(key_path="~/.ssh/lightning_rsa", user=f"s_{studio._studio.id}", host=studio.name)
    # Print the SSH config
    Console().print(f"# ssh s_{studio._studio.id}@ssh.lightning.ai\n\n" + conf)


def _generate_ssh_config(key_path: str, host: str, user: str) -> str:
    return f"""Host {host}
      User {user}
      Hostname ssh.lightning.ai
      IdentityFile {key_path}
      IdentitiesOnly yes
      ServerAliveInterval 15
      ServerAliveCountMax 4
      StrictHostKeyChecking no
      UserKnownHostsFile=/dev/null
    """
