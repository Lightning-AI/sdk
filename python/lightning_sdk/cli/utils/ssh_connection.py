import os
import platform
import uuid
from pathlib import Path
from typing import Optional

from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.utils.config import _DEFAULT_CONFIG_FILE_PATH


def configure_ssh_internal(force_download: bool = False) -> str:
    """Internal function to configure SSH without Click decorators."""
    auth = Auth()
    auth.authenticate()
    return download_ssh_keys(auth.api_key, force_download=force_download)


def download_ssh_keys(
    api_key: Optional[str],
    force_download: bool = False,
    ssh_key_name: str = "lightning_rsa",
) -> str:
    """Download the SSH key for a User."""
    ssh_private_key_path = os.path.join(os.path.expanduser(os.path.dirname(_DEFAULT_CONFIG_FILE_PATH)), ssh_key_name)

    os.makedirs(os.path.dirname(ssh_private_key_path), exist_ok=True)

    if not os.path.isfile(ssh_private_key_path) or force_download:
        key_id = str(uuid.uuid4())
        download_file(
            f"https://lightning.ai/setup/ssh-gen?t={api_key}&id={key_id}&machineName={platform.node()}",
            Path(ssh_private_key_path),
            overwrite=True,
            chmod=0o600,
        )
        download_file(
            f"https://lightning.ai/setup/ssh-public?t={api_key}&id={key_id}",
            Path(ssh_private_key_path + ".pub"),
            overwrite=True,
        )

    return ssh_private_key_path


def download_file(url: str, local_path: Path, overwrite: bool = True, chmod: Optional[int] = None) -> None:
    """Download a file from a URL."""
    import requests

    if os.path.isfile(local_path) and not overwrite:
        raise FileExistsError(f"The file {local_path} already exists and overwrite is set to False.")

    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(local_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)
    if chmod is not None:
        os.chmod(local_path, 0o600)
