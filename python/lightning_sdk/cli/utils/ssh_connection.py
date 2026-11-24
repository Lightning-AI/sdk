"""This machine's Lightning SSH key: created here, and only its public half sent to the platform."""

import platform
import shutil
import subprocess
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

import rich_click as click

from lightning_sdk.api.ssh_key_api import SSHKeyApi, SSHKeyRegistrationError
from lightning_sdk.cli.utils.auth import require_auth_header
from lightning_sdk.lightning_cloud import env

# The web UI's setup script uses the same file, so the browser and CLI flows share one key per machine.
SSH_KEY_NAME = "lightning_ed25519"
_ACCOUNT_SSH_KEYS_PATH = "/me/settings/keys"
_MAX_KEY_NAME_LENGTH = 256


@dataclass(frozen=True)
class LocalSSHKey:
    path: Path
    public_key: str
    # A 403 refuses the signed-in credential, not the key: the account may already have the key, added in the
    # browser, so SSH decides.
    add_refused: bool = False

    @property
    def public_key_path(self) -> Path:
        return self.path.with_suffix(".pub")


def ssh_key_path() -> Path:
    return Path.home() / ".ssh" / SSH_KEY_NAME


def configure_ssh_internal() -> str:
    """Make sure this machine's SSH key exists and is registered to the signed-in user, and return its path.

    For commands that run ``ssh`` straight after: if the key can't be added from here, says where to add it first.
    """
    require_auth_header()
    key = ensure_ssh_key()
    if key.add_refused:
        click.echo(add_key_in_browser_message(key, rerun=True), err=True)
    return str(key.path)


def ensure_ssh_key() -> LocalSSHKey:
    """Create the SSH key if it's missing, and register its public key with the signed-in user's account.

    The private key is never replaced. The platform returns the key unchanged when the account already has it,
    so this is safe to call on every connect. When the signed-in credential isn't allowed to add keys, the result
    says so rather than raising, and the caller tells the user where to add it.
    """
    key_path = ssh_key_path()
    public_key_path = key_path.with_suffix(".pub")
    if not key_path.exists():
        _generate_key(key_path)
        click.echo(f"Created SSH key {key_path}", err=True)
    if not public_key_path.exists():
        _write_public_key(key_path, public_key_path)

    public_key = public_key_path.read_text().strip()
    try:
        SSHKeyApi().create_public_key(name=_key_name(public_key), public_key=public_key)
    except SSHKeyRegistrationError as e:
        if e.status != HTTPStatus.FORBIDDEN:
            raise click.ClickException(
                f"Could not add the SSH key {public_key_path} to your Lightning account: {e}"
            ) from None
        return LocalSSHKey(key_path, public_key, add_refused=True)
    return LocalSSHKey(key_path, public_key)


def add_key_in_browser_message(key: LocalSSHKey, rerun: bool = False) -> str:
    """Where to add ``key`` on lightning.ai; with ``rerun``, to then run the command again."""
    keys_url = env.LIGHTNING_CLOUD_URL.rstrip("/") + _ACCOUNT_SSH_KEYS_PATH
    then = " and run this command again" if rerun else ""
    return (
        "Your Lightning login can't add SSH keys to your account.\n"
        f"If you haven't added {key.public_key_path} yet, add it at {keys_url}{then}. Its public key is:\n"
        f"{key.public_key}"
    )


def _ssh_keygen() -> str:
    path = shutil.which("ssh-keygen")
    if path is None:
        raise click.ClickException("ssh-keygen was not found. Install OpenSSH and run this again.")
    return path


def _generate_key(key_path: Path) -> None:
    key_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # No passphrase, so `lightning studio ssh` works without a terminal. stdin is closed so ssh-keygen
    # can't prompt: if another process creates the key first, it refuses to overwrite it.
    result = subprocess.run(
        [_ssh_keygen(), "-q", "-t", "ed25519", "-N", "", "-C", _default_comment(), "-f", str(key_path)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise click.ClickException(f"ssh-keygen could not create {key_path}: {result.stderr.strip()}")


def _write_public_key(key_path: Path, public_key_path: Path) -> None:
    # Inherits the terminal so ssh-keygen can ask for the passphrase of a key made with one.
    result = subprocess.run([_ssh_keygen(), "-y", "-f", str(key_path)], stdout=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise click.ClickException(f"ssh-keygen could not read the public key from {key_path}")
    public_key_path.write_text(result.stdout)


def _default_comment() -> str:
    # The web UI's script comments keys the same way, and the comment becomes the key's name.
    return f"lightning@{platform.node()}"[:_MAX_KEY_NAME_LENGTH]


def _key_name(public_key: str) -> str:
    fields = public_key.split(maxsplit=2)
    comment = fields[2].strip() if len(fields) > 2 else ""
    return (comment or _default_comment())[:_MAX_KEY_NAME_LENGTH]
