import platform
import uuid
from pathlib import Path
from typing import Optional, Union

from rich.console import Console

from lightning_sdk.cli.generate import _Generate
from lightning_sdk.lightning_cloud.login import Auth


def _download_file(url: str, local_path: Path, overwrite: bool = True, chmod: Optional[int] = None) -> None:
    """Download a file from a URL."""
    import requests

    if local_path.exists() and not overwrite:
        raise FileExistsError(f"The file {local_path} already exists and overwrite is set to False.")

    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(local_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)
    if chmod is not None:
        local_path.chmod(0o600)


class _Configure(_Generate):
    """Configure lightning products."""

    @staticmethod
    def _download_ssh_keys(
        api_key: str,
        key_id: str = "",
        ssh_home: Union[str, Path] = "",
        ssh_key_name: str = "lightning_rsa",
        overwrite: bool = False,
    ) -> None:
        if not ssh_home:
            ssh_home = Path.home() / ".ssh"
        elif isinstance(ssh_home, str):
            ssh_home = Path(ssh_home)
        if not key_id:
            key_id = str(uuid.uuid4())

        path_key = ssh_home / ssh_key_name
        path_pub = ssh_home / f"{ssh_key_name}.pub"

        # todo: consider hitting the API to get the key pair directly instead of using wget
        _download_file(
            f"https://lightning.ai/setup/ssh-gen?t={api_key}&id={key_id}&machineName={platform.node()}",
            path_key,
            overwrite=overwrite,
            chmod=0o600,
        )
        _download_file(f"https://lightning.ai/setup/ssh-public?t={api_key}&id={key_id}", path_pub, overwrite=overwrite)

    def ssh(self, overwrite: bool = False, ssh_key_name: str = "lightning_rsa") -> None:
        """Get SSH config entry for a studio.

        Args:
            overwrite: Whether to overwrite the SSH key and config if they already exist.
            ssh_key_name: The name of the SSH key to generate
        """
        auth = Auth()
        auth.authenticate()
        console = Console()
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(parents=True, exist_ok=True)

        key_path = ssh_dir / ssh_key_name
        config_path = ssh_dir / "config"

        # Check if the SSH key already exists
        if key_path.exists() and (key_path.with_suffix(".pub")).exists() and not overwrite:
            console.print(f"SSH key already exists at {key_path}")
        else:
            self._download_ssh_keys(auth.api_key, ssh_home=ssh_dir, ssh_key_name=ssh_key_name, overwrite=overwrite)
            console.print(f"SSH key generated and saved to {key_path}")

        # Check if the SSH config already contains the required configuration
        config_content = self._generate_ssh_config(str(key_path))
        if config_path.exists():
            with config_path.open("r") as config_file:
                if config_content.strip() in config_file.read():
                    console.print("SSH config already contains the required configuration.")
                    return

        with config_path.open("a") as config_file:
            config_file.write(config_content)
            console.print(f"SSH config updated at {config_path}")
