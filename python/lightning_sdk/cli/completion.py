"""Install and manage shell completion scripts."""

import os
import shutil
from pathlib import Path
from typing import Optional

import rich_click as click
from click.shell_completion import get_completion_class

from lightning_sdk.cli.utils.logging import LightningCommand, LightningGroup

_SHELLS = ("bash", "zsh", "fish")
_BLOCK_START = "# >>> lightning completion >>>"
_BLOCK_END = "# <<< lightning completion <<<"


@click.group("completion", cls=LightningGroup)
def completion() -> None:
    """Install and manage native shell completion."""


@completion.command("install", cls=LightningCommand)
@click.option("--shell", "shell_name", type=click.Choice(_SHELLS), help="Shell to configure.")
@click.pass_context
def install(ctx: click.Context, shell_name: Optional[str]) -> None:
    """Install completion for Bash, Zsh, or Fish."""
    selected_shell = _resolve_shell(shell_name)
    script_path = _script_path(selected_shell)
    rc_path = _rc_path(selected_shell)
    if rc_path is not None:
        _validate_rc_block(rc_path)

    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(_completion_source(ctx.find_root().command, selected_shell))

    if rc_path is not None:
        _install_rc_block(rc_path, _rc_block(selected_shell))

    click.echo(f"Installed Lightning completion for {selected_shell.capitalize()}.")
    click.echo(f"Completion script: {script_path}")
    if rc_path is not None:
        click.echo(f"Shell configuration: {rc_path}")
    click.echo(f"Restart your shell with: exec {selected_shell}")


@completion.command("status", cls=LightningCommand)
@click.option("--shell", "shell_name", type=click.Choice(_SHELLS), help="Shell to inspect.")
def status(shell_name: Optional[str]) -> None:
    """Show whether completion is installed."""
    selected_shell = _resolve_shell(shell_name)
    script_path = _script_path(selected_shell)
    rc_path = _rc_path(selected_shell)
    script_installed = script_path.is_file()
    rc_installed = rc_path is None or _has_rc_block(rc_path)

    if script_installed and rc_installed:
        click.echo(f"Lightning completion is installed for {selected_shell.capitalize()}.")
        click.echo(f"Completion script: {script_path}")
        if rc_path is not None:
            click.echo(f"Shell configuration: {rc_path}")
        return

    missing = []
    if not script_installed:
        missing.append(f"completion script {script_path}")
    if not rc_installed and rc_path is not None:
        missing.append(f"managed block in {rc_path}")
    raise click.ClickException(
        f"Lightning completion is not installed for {selected_shell}: missing {', '.join(missing)}"
    )


@completion.command("uninstall", cls=LightningCommand)
@click.option("--shell", "shell_name", type=click.Choice(_SHELLS), help="Shell to remove.")
def uninstall(shell_name: Optional[str]) -> None:
    """Remove installed completion and its managed shell configuration."""
    selected_shell = _resolve_shell(shell_name)
    script_path = _script_path(selected_shell)
    rc_path = _rc_path(selected_shell)
    changed = False

    if rc_path is not None:
        _validate_rc_block(rc_path, action="uninstalling")

    if script_path.is_file():
        script_path.unlink()
        changed = True
    if rc_path is not None and _remove_rc_block(rc_path):
        changed = True

    if changed:
        click.echo(f"Uninstalled Lightning completion for {selected_shell.capitalize()}.")
    else:
        click.echo(f"Lightning completion was not installed for {selected_shell.capitalize()}.")


def _resolve_shell(shell_name: Optional[str]) -> str:
    if shell_name is not None:
        return shell_name

    detected = Path(os.environ.get("SHELL", "")).name
    if detected in _SHELLS:
        return detected
    raise click.UsageError("Could not detect a supported shell. Pass --shell bash, --shell zsh, or --shell fish.")


def _home() -> Path:
    return Path(os.environ.get("HOME") or Path.home()).expanduser()


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or _home() / ".config").expanduser()


def _script_path(shell_name: str) -> Path:
    if shell_name == "fish":
        return _config_home() / "fish" / "completions" / "lightning.fish"
    return _config_home() / "lightning" / "completions" / f"lightning.{shell_name}"


def _rc_path(shell_name: str) -> Optional[Path]:
    if shell_name == "fish":
        return None
    if shell_name == "zsh":
        return Path(os.environ.get("ZDOTDIR") or _home()).expanduser() / ".zshrc"
    return _home() / ".bashrc"


def _completion_source(root_command: click.Command, shell_name: str) -> str:
    completion_class = get_completion_class(shell_name)
    if completion_class is None:
        raise click.ClickException(f"Completion is not available for {shell_name}.")
    shell_completion = completion_class(root_command, {}, "lightning", "_LIGHTNING_COMPLETE")
    return shell_completion.source_template % shell_completion.source_vars()


def _rc_block(shell_name: str) -> str:
    relative_path = f"lightning/completions/lightning.{shell_name}"
    source_command = "source" if shell_name == "zsh" else "."
    shell_setup = "autoload -Uz compinit\n(( $+functions[compdef] )) || compinit\n" if shell_name == "zsh" else ""
    return (
        f"{_BLOCK_START}\n"
        f"{shell_setup}"
        f'_lightning_completion_file="${{XDG_CONFIG_HOME:-${{HOME}}/.config}}/{relative_path}"\n'
        'if [ -r "${_lightning_completion_file}" ]; then\n'
        f'  {source_command} "${{_lightning_completion_file}}"\n'
        "fi\n"
        "unset _lightning_completion_file\n"
        f"{_BLOCK_END}\n"
    )


def _has_rc_block(rc_path: Path) -> bool:
    if not rc_path.is_file():
        return False
    contents = rc_path.read_text()
    return _BLOCK_START in contents and _BLOCK_END in contents


def _backup(rc_path: Path) -> Path:
    backup_path = Path(f"{rc_path}.lightning.bak")
    shutil.copy2(rc_path, backup_path)
    return backup_path


def _install_rc_block(rc_path: Path, block: str) -> None:
    rc_path.parent.mkdir(parents=True, exist_ok=True)
    _validate_rc_block(rc_path)
    contents = rc_path.read_text() if rc_path.is_file() else ""
    if _BLOCK_START in contents:
        return

    if rc_path.is_file():
        _backup(rc_path)
    prefix = contents.rstrip("\n")
    rc_path.write_text(f"{prefix}\n\n{block}" if prefix else block)


def _validate_rc_block(rc_path: Path, action: str = "installing") -> None:
    if not rc_path.is_file():
        return
    contents = rc_path.read_text()
    if (_BLOCK_START in contents) != (_BLOCK_END in contents):
        raise click.ClickException(f"Incomplete Lightning completion block in {rc_path}; repair it before {action}.")


def _remove_rc_block(rc_path: Path) -> bool:
    if not rc_path.is_file():
        return False

    contents = rc_path.read_text()
    start = contents.find(_BLOCK_START)
    end = contents.find(_BLOCK_END)
    if start == -1 and end == -1:
        return False
    if start == -1 or end == -1 or end < start:
        raise click.ClickException(
            f"Incomplete Lightning completion block in {rc_path}; repair it before uninstalling."
        )

    end += len(_BLOCK_END)
    if end < len(contents) and contents[end] == "\n":
        end += 1
    if start > 0 and contents[start - 1] == "\n":
        start -= 1

    _backup(rc_path)
    rc_path.write_text(contents[:start] + contents[end:])
    return True
