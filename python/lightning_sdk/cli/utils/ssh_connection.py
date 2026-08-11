import os
import platform
import subprocess
import uuid
from pathlib import Path
from typing import List, Optional

import rich_click as click

from lightning_sdk.cli.utils.auth import require_auth_header
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.utils.config import _DEFAULT_CONFIG_FILE_PATH

_SSH_HOST = "ssh.lightning.ai"
_DEFAULT_SSH_OPTIONS = [
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "StrictHostKeyChecking=no",
    "-o", "LogLevel=ERROR",
]


def configure_ssh_internal(force_download: bool = False) -> str:
    """Internal function to configure SSH without Click decorators."""
    auth = Auth()
    require_auth_header()
    if not auth.api_key and not auth.load():
        raise click.UsageError("An API key is required. Run `lightning login` first.")
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


def exec_ssh(
    user: str,
    host: str = _SSH_HOST,
    *,
    remote_command: Optional[str] = None,
    extra_options: Optional[List[str]] = None,
    tty: bool = False,
) -> subprocess.CompletedProcess:
    """Run an SSH session to a Lightning machine.

    Args:
        user: SSH user to connect as (e.g. ``s_<studio_id>`` or ``j_<job_id>``).
        host: SSH host; defaults to ``ssh.lightning.ai``.
        remote_command: Optional command to run on the remote host.
            When omitted, opens an interactive shell.
        extra_options: Additional ``-o``-style SSH options (e.g. ``["Port=2222"]``).
        tty: Force pseudo-terminal allocation (``-tt``). Required for interactive
            editors and other TUI programs.

    Returns:
        The ``CompletedProcess`` from ``subprocess.run``.

    Raises:
        RuntimeError: If the SSH connection fails even after retrying with fresh keys.
        FileNotFoundError: If the ``ssh`` binary is not on ``PATH``.
    """
    ssh_key_path = configure_ssh_internal()

    def _build_cmd(key_path: str) -> List[str]:
        cmd: List[str] = ["ssh", "-i", key_path]
        cmd.extend(_DEFAULT_SSH_OPTIONS)
        if tty:
            cmd.append("-tt")
        if extra_options:
            for opt in extra_options:
                cmd.extend(["-o", opt])
        cmd.append(f"{user}@{host}")
        if remote_command is not None:
            cmd.append(remote_command)
        return cmd

    def _run(key_path: str) -> subprocess.CompletedProcess:
        return subprocess.run(_build_cmd(key_path))

    try:
        return _run(ssh_key_path)
    except FileNotFoundError:
        raise
    except Exception:
        # Redownload keys in case they are stale, then retry once.
        ssh_key_path = configure_ssh_internal(force_download=True)
        try:
            return _run(ssh_key_path)
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise RuntimeError("Failed to establish SSH connection") from exc


def _studio_ssh_user(studio_id: str) -> str:
    """Build the SSH user string for a Studio (``s_<id>``)."""
    return f"s_{studio_id}"


def _job_ssh_user(job_id: str) -> str:
    """Build the SSH user string for a Job (``j_<id>``).

    Handles both ``job_<ulid>`` and plain ``<ulid>`` ids.
    """
    prefix = "job_"
    suffix = job_id[len(prefix):] if job_id.startswith(prefix) else job_id
    return f"j_{suffix}"
