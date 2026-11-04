import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.api.ssh_key_api import SSHKeyRegistrationError
from lightning_sdk.cli.ssh.common import add_ssh_config, host_uses_ssh_key
from tests.cli.help import assert_help_contains, mock_command_logging


def test_legacy_configure_requires_login_without_authentication_fallback() -> None:
    """Legacy SSH configuration must not start callback authentication when credentials are missing."""
    from unittest.mock import MagicMock, patch

    import pytest
    import rich_click as click

    from lightning_sdk.cli.legacy.configure import _configure_ssh_internal

    authenticate = MagicMock(side_effect=AssertionError("callback authentication must not start"))
    with patch(
        "lightning_sdk.cli.legacy.configure.require_auth_header",
        side_effect=click.UsageError("Run `lightning login` first."),
    ), patch("lightning_sdk.lightning_cloud.login.Auth.authenticate", authenticate), pytest.raises(
        click.UsageError, match="lightning login"
    ):
        _configure_ssh_internal()

    authenticate.assert_not_called()


def test_legacy_connect_reaches_non_browser_credential_boundary() -> None:
    """Legacy Studio connect must fail before its SSH subprocess when login is required."""
    from unittest.mock import MagicMock, patch

    import pytest
    import rich_click as click

    from lightning_sdk.cli.legacy.connect import studio

    authenticate = MagicMock(side_effect=AssertionError("callback authentication must not start"))
    with patch(
        "lightning_sdk.cli.legacy.configure.require_auth_header",
        side_effect=click.UsageError("Run `lightning login` first."),
    ), patch("lightning_sdk.lightning_cloud.login.Auth.authenticate", authenticate), patch(
        "lightning_sdk.cli.legacy.connect.subprocess.run",
        side_effect=AssertionError("SSH must not start without credentials"),
    ), pytest.raises(click.UsageError, match="lightning login"):
        studio.callback(name=None, teamspace=None)

    authenticate.assert_not_called()


def test_configure_resolves_studio_before_authentication() -> None:
    """An unresolved studio does not check credentials or create a key."""
    from unittest.mock import MagicMock, patch

    import pytest
    import rich_click as click

    from lightning_sdk.cli.ssh.configure import configure_ssh

    require_auth_header = MagicMock()
    ensure_ssh_key = MagicMock()
    with patch(
        "lightning_sdk.cli.ssh.configure.resolve_teamspace",
        return_value=MagicMock(),
    ), patch(
        "lightning_sdk.cli.ssh.configure.resolve_studio",
        side_effect=click.UsageError("Unknown studio"),
    ), patch("lightning_sdk.cli.ssh.configure.require_auth_header", require_auth_header), patch(
        "lightning_sdk.cli.ssh.configure.ensure_ssh_key", ensure_ssh_key
    ), pytest.raises(click.UsageError, match="Unknown studio"):
        configure_ssh.callback(name="missing")

    require_auth_header.assert_not_called()
    ensure_ssh_key.assert_not_called()


@mock_command_logging
def test_ssh_configure_help() -> None:
    assert_help_contains(
        "lightning ssh configure --help", "Usage: lightning ssh configure", "Get SSH config entry for a studio."
    )


@mock_command_logging
def test_configure_help() -> None:
    text = assert_help_contains(
        "lightning configure --help",
        "`lightning configure` has moved to noun-first commands:",
        "ssh -> lightning ssh configure",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_configure_ssh_legacy_help() -> None:
    assert_help_contains(
        "lightning configure ssh --help",
        "Deprecation warning:",
        "Use `lightning ssh configure` instead of `lightning configure ssh`.",
        "Usage: lightning configure ssh [OPTIONS]",
    )


needs_ssh_keygen = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="needs OpenSSH's ssh-keygen")

OLD_RSA_ENTRY = """Host dev
      User s_studio-id
      Hostname ssh.lightning.ai
      IdentityFile /home/me/.ssh/lightning_rsa
      IdentitiesOnly yes
      ServerAliveInterval 15
      ServerAliveCountMax 4
      StrictHostKeyChecking no
      UserKnownHostsFile=/dev/null
"""


@pytest.fixture()
def home(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture()
def ssh_key_api():
    api = MagicMock()
    with patch("lightning_sdk.cli.utils.ssh_connection.SSHKeyApi", return_value=api), patch(
        "requests.get", side_effect=AssertionError("SSH setup must not download anything")
    ):
        yield api


@pytest.fixture()
def studio():
    studio = MagicMock()
    studio.name = "dev"
    studio._studio.id = "studio-id"
    return studio


def _configure(studio, *args: str):
    from click.testing import CliRunner

    from lightning_sdk.cli.ssh.configure import configure_ssh

    with patch("lightning_sdk.cli.ssh.configure.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.ssh.configure.resolve_studio", return_value=studio
    ), patch("lightning_sdk.cli.ssh.configure.require_auth_header", return_value="Bearer token"):
        return CliRunner().invoke(configure_ssh, ["--name", "dev", *args])


@needs_ssh_keygen
def test_configure_creates_a_local_key_registers_it_and_adds_the_entry(home, ssh_key_api, studio) -> None:
    result = _configure(studio)

    assert result.exit_code == 0, result.output
    key_path = home / ".ssh" / "lightning_ed25519"
    public_key = key_path.with_suffix(".pub").read_text().strip()
    assert public_key.startswith("ssh-ed25519 ")
    ssh_key_api.create_public_key.assert_called_once()
    assert ssh_key_api.create_public_key.call_args.kwargs["public_key"] == public_key
    assert (home / ".ssh" / "config").read_text() == (
        "\n"
        "Host dev\n"
        "  User s_studio-id\n"
        "  Hostname ssh.lightning.ai\n"
        "  IdentityFile ~/.ssh/lightning_ed25519\n"
        "  IdentitiesOnly yes\n"
        "  ServerAliveInterval 15\n"
        "  ServerAliveCountMax 4\n"
        "  StrictHostKeyChecking accept-new\n"
        "  UserKnownHostsFile ~/.ssh/lightning_known_hosts\n"
    )
    assert "Added dev to ~/.ssh/config" in result.output


@needs_ssh_keygen
def test_configure_again_reuses_the_key_and_leaves_the_config(home, ssh_key_api, studio) -> None:
    assert _configure(studio).exit_code == 0
    key_path = home / ".ssh" / "lightning_ed25519"
    private_key = key_path.read_bytes()
    config = (home / ".ssh" / "config").read_text()
    first_registration = ssh_key_api.create_public_key.call_args

    result = _configure(studio, "--overwrite")

    assert result.exit_code == 0, result.output
    assert ssh_key_api.create_public_key.call_count == 2
    assert ssh_key_api.create_public_key.call_args == first_registration
    assert key_path.read_bytes() == private_key
    assert (home / ".ssh" / "config").read_text() == config
    assert "already uses this key for dev" in result.output
    assert "--overwrite no longer replaces the SSH key" in result.output


@needs_ssh_keygen
def test_configure_shows_the_platform_refusal(home, ssh_key_api, studio) -> None:
    refusal = "You can have at most 50 SSH keys. Delete one you no longer use, then add this one again."
    ssh_key_api.create_public_key.side_effect = SSHKeyRegistrationError(refusal)

    result = _configure(studio)

    assert result.exit_code == 1
    # rich wraps the error in a box, so drop its border before matching.
    assert refusal in " ".join(result.output.replace("│", " ").split())
    assert not (home / ".ssh" / "config").exists()


@needs_ssh_keygen
def test_legacy_configure_creates_and_registers_the_same_key(home, ssh_key_api, studio) -> None:
    from lightning_sdk.cli.legacy.configure import _configure_ssh_internal

    with patch("lightning_sdk.cli.legacy.configure.require_auth_header", return_value="Bearer token"), patch(
        "lightning_sdk.cli.legacy.configure.resolve_teamspace", return_value=MagicMock()
    ), patch("lightning_sdk.cli.legacy.configure.resolve_studio", return_value=studio):
        _configure_ssh_internal(name="dev")

    public_key = (home / ".ssh" / "lightning_ed25519.pub").read_text().strip()
    ssh_key_api.create_public_key.assert_called_once()
    assert ssh_key_api.create_public_key.call_args.kwargs["public_key"] == public_key
    assert host_uses_ssh_key((home / ".ssh" / "config").read_text(), "dev")


def test_entry_is_added_after_one_that_only_has_the_old_key(home) -> None:
    config_path = home / ".ssh" / "config"
    config_path.parent.mkdir()
    config_path.write_text(OLD_RSA_ENTRY)

    assert add_ssh_config(host="dev", user="s_studio-id")

    config = config_path.read_text()
    assert config.startswith(OLD_RSA_ENTRY)
    assert host_uses_ssh_key(config, "dev")
    assert not add_ssh_config(host="dev", user="s_studio-id")
    assert config_path.read_text() == config


needs_ssh = pytest.mark.skipif(shutil.which("ssh") is None, reason="needs OpenSSH's ssh")


def _ssh_settings(config_path: Path, host: str) -> list:
    """The settings ssh would use for ``host``, from ``ssh -G``, which doesn't connect."""
    return subprocess.run(
        ["ssh", "-G", "-F", str(config_path), host],
        capture_output=True,
        text=True,
        check=True,
        stdin=subprocess.DEVNULL,
    ).stdout.splitlines()


@needs_ssh
def test_ssh_checks_the_host_key_with_a_new_entry(home) -> None:
    config_path = home / ".ssh" / "config"
    add_ssh_config(host="dev", user="s_studio-id")

    resolved = _ssh_settings(config_path, "dev")

    assert "stricthostkeychecking accept-new" in resolved
    # ssh expands ~ from the user database rather than $HOME, so only the file name is checked.
    known_hosts = [line for line in resolved if line.startswith("userknownhostsfile ")]
    assert len(known_hosts) == 1
    assert known_hosts[0].endswith("/.ssh/lightning_known_hosts")


@needs_ssh
def test_ssh_offers_both_keys_for_a_host_with_an_old_entry(home) -> None:
    config_path = home / ".ssh" / "config"
    config_path.parent.mkdir()
    config_path.write_text(OLD_RSA_ENTRY)
    add_ssh_config(host="dev", user="s_studio-id")

    resolved = _ssh_settings(config_path, "dev")

    identity_files = [line.split(maxsplit=1)[1] for line in resolved if line.startswith("identityfile ")]
    assert identity_files[0] == "/home/me/.ssh/lightning_rsa"
    assert identity_files[1].endswith(".ssh/lightning_ed25519")
    assert "identitiesonly yes" in resolved


@pytest.mark.parametrize(
    ("config", "uses_key"),
    [
        ("Host dev\n  IdentityFile ~/.ssh/lightning_ed25519\n", True),
        ("host other dev\n  identityfile=~/.ssh/lightning_ed25519\n", True),
        ("Host dev-2\n  IdentityFile ~/.ssh/lightning_ed25519\n", False),
        ("Host dev\n  IdentityFile ~/.ssh/lightning_rsa\nHost x\n  IdentityFile ~/.ssh/lightning_ed25519\n", False),
        ("", False),
    ],
)
def test_host_uses_ssh_key(config: str, uses_key: bool) -> None:
    assert host_uses_ssh_key(config, "dev") is uses_key
