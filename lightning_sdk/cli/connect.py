import subprocess
import sys
from typing import Optional

from lightning_sdk.cli.configure import _Configure
from lightning_sdk.lightning_cloud.login import Auth


class _Connect(_Configure):
    """Connect to lightning products."""

    def studio(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Connect to a studio via SSH.

        Args:
            name: The name of the studio to connect to.
            teamspace: The teamspace the studio is part of. Should be of format <OWNER>/<TEAMSPACE_NAME>.
        """
        auth = Auth()
        auth.authenticate()  # this is maybe not needed
        studio = self._get_studio(name=name, teamspace=teamspace)
        host = "ssh.lightning.ai"
        username = f"s_{studio._studio.id}"

        self.ssh(overwrite=False)

        try:
            subprocess.run(["ssh", f"{username}@{host}"])
        except Exception as ex:
            print(f"Failed to establish SSH connection: {ex}")
            sys.exit(1)
