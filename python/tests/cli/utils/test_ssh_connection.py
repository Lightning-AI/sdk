import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import rich_click as click

from lightning_sdk.api.ssh_key_api import SSHKeyRegistrationError
from lightning_sdk.cli.utils.ssh_connection import configure_ssh_internal, ensure_ssh_key

needs_ssh_keygen = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="needs OpenSSH's ssh-keygen")


@pytest.fixture()
def home(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture()
def api():
    api = MagicMock()
    with patch("lightning_sdk.cli.utils.ssh_connection.SSHKeyApi", return_value=api):
        yield api


def _make_key(path: Path, comment: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", comment, "-f", str(path)],
        check=True,
        stdin=subprocess.DEVNULL,
    )


@needs_ssh_keygen
def test_creates_an_ed25519_key_without_a_passphrase_and_registers_it(home, api) -> None:
    key_path = ensure_ssh_key()

    assert key_path == home / ".ssh" / "lightning_ed25519"
    public_key = key_path.with_suffix(".pub").read_text().strip()
    key_type, _, comment = public_key.split(maxsplit=2)
    assert key_type == "ssh-ed25519"
    assert comment == f"lightning@{platform.node()}"
    if os.name == "posix":
        assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    # No passphrase: reading the key back needs no terminal.
    subprocess.run(["ssh-keygen", "-y", "-f", str(key_path)], check=True, stdin=subprocess.DEVNULL, capture_output=True)
    api.create_public_key.assert_called_once_with(name=comment, public_key=public_key)


@needs_ssh_keygen
def test_a_second_run_registers_the_same_key_again(home, api) -> None:
    """The platform returns a key the account already has, so a repeat needs no check here."""
    first = ensure_ssh_key()
    private_key = first.read_bytes()

    assert ensure_ssh_key() == first

    assert first.read_bytes() == private_key
    assert api.create_public_key.call_count == 2
    assert api.create_public_key.call_args_list[0] == api.create_public_key.call_args_list[1]


@needs_ssh_keygen
def test_registers_an_existing_key_under_its_comment_without_replacing_it(home, api) -> None:
    key_path = home / ".ssh" / "lightning_ed25519"
    _make_key(key_path, "lightning@made-by-the-web-ui")
    private_key = key_path.read_bytes()

    ensure_ssh_key()

    assert key_path.read_bytes() == private_key
    api.create_public_key.assert_called_once_with(
        name="lightning@made-by-the-web-ui", public_key=key_path.with_suffix(".pub").read_text().strip()
    )


@needs_ssh_keygen
def test_recreates_a_missing_public_key_from_the_private_key(home, api) -> None:
    key_path = home / ".ssh" / "lightning_ed25519"
    _make_key(key_path, "lightning@laptop")
    public_key = key_path.with_suffix(".pub").read_text()
    private_key = key_path.read_bytes()
    key_path.with_suffix(".pub").unlink()

    ensure_ssh_key()

    assert key_path.read_bytes() == private_key
    assert key_path.with_suffix(".pub").read_text().split()[:2] == public_key.split()[:2]
    api.create_public_key.assert_called_once()


@needs_ssh_keygen
def test_shows_the_platform_refusal(home, api) -> None:
    refusal = "This SSH public key can't be added. Please generate a new key and add that instead."
    api.create_public_key.side_effect = SSHKeyRegistrationError(refusal)

    with pytest.raises(click.ClickException) as error:
        ensure_ssh_key()

    assert refusal in error.value.message
    assert "lightning_ed25519.pub" in error.value.message


def test_explains_a_missing_ssh_keygen(home, api) -> None:
    with patch("lightning_sdk.cli.utils.ssh_connection.shutil.which", return_value=None), pytest.raises(
        click.ClickException, match="ssh-keygen was not found"
    ):
        ensure_ssh_key()

    api.create_public_key.assert_not_called()


def test_configure_requires_login_first(home, api) -> None:
    with patch(
        "lightning_sdk.cli.utils.ssh_connection.require_auth_header",
        side_effect=click.UsageError("Run `lightning login` first."),
    ), pytest.raises(click.UsageError, match="lightning login"):
        configure_ssh_internal()

    assert not (home / ".ssh").exists()
    api.create_public_key.assert_not_called()


def test_cli_has_no_setup_token_routes() -> None:
    """Keys are made locally: nothing asks the server for one, or puts a credential in a URL."""
    import lightning_sdk.cli

    cli_dir = Path(lightning_sdk.cli.__file__).parent
    for source in cli_dir.rglob("*.py"):
        text = source.read_text()
        assert "/setup/ssh" not in text, source
        assert "?t=" not in text, source
