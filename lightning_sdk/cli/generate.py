from typing import Optional

from rich.console import Console

from lightning_sdk.cli.studios_menu import _StudiosMenu


class _Generate(_StudiosMenu):
    """Generate configs (such as ssh for studio) and print them to commandline."""

    def ssh(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Get SSH config entry for a studio.

        Args:
            name: The name of the studio to obtain SSH config.
                If not specified, tries to infer from the environment (e.g. when run from within a Studio.)
            teamspace: The teamspace the studio is part of. Should be of format <OWNER>/<TEAMSPACE_NAME>.
                If not specified, tries to infer from the environment (e.g. when run from within a Studio.)
        """
        studio = self._get_studio(name=name, teamspace=teamspace)

        # Print the SSH config
        studio_id = studio._studio.id
        config = f"""# ssh s_{studio_id}@ssh.lightning.ai

Host {name}
  User s_{studio_id}
  Hostname ssh.lightning.ai
  IdentityFile ~/.ssh/lightning_rsa
  IdentitiesOnly yes
  ServerAliveInterval 15
  ServerAliveCountMax 4
  StrictHostKeyChecking no
  UserKnownHostsFile=/dev/null"""
        Console().print(config)
