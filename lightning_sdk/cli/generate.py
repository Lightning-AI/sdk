from typing import Optional

from rich.console import Console

from lightning_sdk import Studio


class _Generate:
    """Generate configs (such as ssh for studio) and print them to commandline."""

    console = Console()

    def _generate_ssh_config(self, name: str, studio_id: str) -> str:
        """Generate SSH config entry for the studio.

        Args:
            name: Studio name
            studio_id: Studio space ID

        Returns:
            str: SSH config entry
        """
        return f"""# ssh s_{studio_id}@ssh.lightning.ai

Host {name}
  User s_{studio_id}
  Hostname ssh.lightning.ai
  IdentityFile ~/.ssh/lightning_rsa
  IdentitiesOnly yes
  ServerAliveInterval 15
  ServerAliveCountMax 4
  StrictHostKeyChecking no
  UserKnownHostsFile=/dev/null"""

    def ssh(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Get SSH config entry for a studio. Will start the studio if needed.

        Args:
            name: The name of the studio to stop.
                If not specified, tries to infer from the environment (e.g. when run from within a Studio.)
            teamspace: The teamspace the studio is part of. Should be of format <OWNER>/<TEAMSPACE_NAME>.
                If not specified, tries to infer from the environment (e.g. when run from within a Studio.)
        """
        if teamspace:
            ts_splits = teamspace.split("/")
            if len(ts_splits) != 2:
                raise ValueError(f"Teamspace should be of format <OWNER>/<TEAMSPACE_NAME> but got {teamspace}")
            owner, teamspace = ts_splits
        else:
            owner, teamspace = None, None

        try:
            studio = Studio(name=name, teamspace=teamspace, org=owner, user=None, create_ok=False)
        except (RuntimeError, ValueError):
            studio = Studio(name=name, teamspace=teamspace, org=None, user=owner, create_ok=False)

        # Print the SSH config
        self.console.print(self._generate_ssh_config(name, studio._studio.id))
