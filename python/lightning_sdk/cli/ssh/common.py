"""Shared SSH command helpers."""


def generate_ssh_config(key_path: str, host: str, user: str) -> str:
    return f"""Host {host}
      User {user}
      Hostname ssh.lightning.ai
      IdentityFile {key_path}
      IdentitiesOnly yes
      ServerAliveInterval 15
      ServerAliveCountMax 4
      StrictHostKeyChecking no
      UserKnownHostsFile=/dev/null
    """
