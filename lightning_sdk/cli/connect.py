import subprocess
import sys
from typing import Optional

from lightning_sdk.cli.configure import _Configure


class _Connect(_Configure):
    """Connect to lightning products."""

    def studio(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Connect to a studio via SSH.

        Args:
            name: The name of the studio to connect to.
            teamspace: The teamspace the studio is part of. Should be of format <OWNER>/<TEAMSPACE_NAME>.
        """
        self.ssh(name=name, teamspace=teamspace, overwrite=False)
        studio = self._get_studio(name=name, teamspace=teamspace)

        try:
            subprocess.run(["ssh", studio.name])
        except Exception as ex:
            print(f"Failed to establish SSH connection: {ex}")
            sys.exit(1)
