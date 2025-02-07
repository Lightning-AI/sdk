import os
import platform
import subprocess
import sys
from typing import Optional

from lightning_sdk.cli.studios_menu import _StudiosMenu
from lightning_sdk.lightning_cloud.env import LIGHTNING_CLOUD_URL
from lightning_sdk.lightning_cloud.login import Auth


class _Connect(_StudiosMenu):
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
        studio_id = studio._studio.id
        host = "ssh.lightning.ai"
        username = f"s_{studio_id}"

        # Uniq -> `curl -s "${host}/setup/ssh?t=${credentials?.gridUserKey}&s=${cloudSpace?.id}" | bash`;
        # Win ->  `iwr "${host}/setup/ssh-windows?t=${credentials?.gridUserKey}&s=${cloudSpace?.id}" -useb | iex`;
        # os switches between Unix and Windows
        if platform.system() == "Windows":
            os.system(f"iwr '{LIGHTNING_CLOUD_URL}/setup/ssh-windows?t={auth.api_key}&s={studio_id}' -useb | iex")
        else:
            os.system(f"curl -s '{LIGHTNING_CLOUD_URL}/setup/ssh?t={auth.api_key}&s={studio_id}' | bash")

        try:
            subprocess.run(["ssh", f"{username}@{host}"])
        except Exception as e:
            print(f"Failed to establish SSH connection: {e}")
            sys.exit(1)
