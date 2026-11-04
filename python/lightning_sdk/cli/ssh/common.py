"""Shared SSH command helpers."""

from pathlib import Path

from lightning_sdk.cli.utils.ssh_connection import SSH_KEY_NAME

SSH_HOST = "ssh.lightning.ai"


def generate_ssh_config(host: str, user: str) -> str:
    """The ``~/.ssh/config`` entry for ``host``, in the same form as the web UI's setup script writes."""
    return (
        f"Host {host}\n"
        f"  User {user}\n"
        f"  Hostname {SSH_HOST}\n"
        f"  IdentityFile ~/.ssh/{SSH_KEY_NAME}\n"
        "  IdentitiesOnly yes\n"
        "  ServerAliveInterval 15\n"
        "  ServerAliveCountMax 4\n"
        "  StrictHostKeyChecking no\n"
        "  UserKnownHostsFile /dev/null\n"
    )


def host_uses_ssh_key(config: str, host: str) -> bool:
    """Whether a ``Host`` or ``Match`` block naming ``host`` already has the Lightning key as an ``IdentityFile``."""
    in_block = False
    for line in config.splitlines():
        fields = line.split()
        if not fields:
            continue
        keyword = fields[0].lower()
        if keyword in ("host", "match"):
            in_block = host in fields[1:]
        elif in_block and keyword.startswith("identityfile") and f".ssh/{SSH_KEY_NAME}" in line:
            return True
    return False


def add_ssh_config(host: str, user: str) -> bool:
    """Append the entry for ``host`` to ``~/.ssh/config``, unless one there already uses the Lightning key.

    ssh tries every ``IdentityFile`` of every block that matches, so an older entry for ``host`` that names
    only ``lightning_rsa`` offers both keys once this one is added after it.

    Returns:
        Whether the file was changed.
    """
    config_path = Path.home() / ".ssh" / "config"
    config = config_path.read_text() if config_path.exists() else ""
    if host_uses_ssh_key(config, host):
        return False
    config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with config_path.open("a") as config_file:
        if config and not config.endswith("\n"):
            config_file.write("\n")
        config_file.write("\n" + generate_ssh_config(host=host, user=user))
    return True
