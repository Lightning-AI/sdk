from pathlib import Path

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli


def _environment(tmp_path: Path, shell: str) -> dict[str, str | None]:
    return {
        "HOME": str(tmp_path / "home"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "SHELL": f"/bin/{shell}",
        "ZDOTDIR": None,
    }


def test_zsh_install_is_static_idempotent_and_reversible(tmp_path):
    environment = _environment(tmp_path, "zsh")
    home = Path(environment["HOME"])
    home.mkdir()
    rc_path = home / ".zshrc"
    rc_path.write_text("setopt interactive_comments\n")
    runner = CliRunner()

    installed = runner.invoke(main_cli, ["completion", "install"], env=environment)

    assert installed.exit_code == 0
    assert "Installed Lightning completion for Zsh." in installed.output
    script_path = tmp_path / "config/lightning/completions/lightning.zsh"
    assert "_lightning_completion()" in script_path.read_text()
    assert "remote_directories" in script_path.read_text()
    assert "compadd -S ''" in script_path.read_text()
    assert rc_path.read_text().count("# >>> lightning completion >>>") == 1
    assert "(( $+functions[compdef] )) || compinit" in rc_path.read_text()
    assert (home / ".zshrc.lightning.bak").read_text() == "setopt interactive_comments\n"

    installed_again = runner.invoke(main_cli, ["completion", "install"], env=environment)
    status = runner.invoke(main_cli, ["completion", "status"], env=environment)

    assert installed_again.exit_code == 0
    assert rc_path.read_text().count("# >>> lightning completion >>>") == 1
    assert status.exit_code == 0
    assert "Lightning completion is installed for Zsh." in status.output

    removed = runner.invoke(main_cli, ["completion", "uninstall"], env=environment)

    assert removed.exit_code == 0
    assert "Uninstalled Lightning completion for Zsh." in removed.output
    assert not script_path.exists()
    assert rc_path.read_text() == "setopt interactive_comments\n"


def test_zsh_install_uses_zdotdir(tmp_path):
    environment = _environment(tmp_path, "zsh")
    environment["ZDOTDIR"] = str(tmp_path / "zsh")
    runner = CliRunner()

    result = runner.invoke(main_cli, ["completion", "install"], env=environment)

    assert result.exit_code == 0
    assert (tmp_path / "zsh/.zshrc").is_file()
    assert not (Path(environment["HOME"]) / ".zshrc").exists()


def test_bash_install_writes_script_and_managed_bashrc_block(tmp_path):
    environment = _environment(tmp_path, "bash")
    runner = CliRunner()

    result = runner.invoke(main_cli, ["completion", "install"], env=environment)

    assert result.exit_code == 0
    script_path = tmp_path / "config/lightning/completions/lightning.bash"
    assert "compopt -o nospace" in script_path.read_text()
    bashrc = (tmp_path / "home/.bashrc").read_text()
    assert '. "${_lightning_completion_file}"' in bashrc


def test_fish_install_uses_native_autoload_directory_without_rc_file(tmp_path):
    environment = _environment(tmp_path, "fish")
    runner = CliRunner()

    installed = runner.invoke(main_cli, ["completion", "install"], env=environment)
    status = runner.invoke(main_cli, ["completion", "status"], env=environment)

    assert installed.exit_code == 0
    assert status.exit_code == 0
    script_path = tmp_path / "config/fish/completions/lightning.fish"
    assert script_path.is_file()
    assert "--command lightning" in script_path.read_text()
    assert not (tmp_path / "home/.config/fish/config.fish").exists()


def test_shell_option_overrides_detection(tmp_path):
    environment = _environment(tmp_path, "unsupported")

    result = CliRunner().invoke(main_cli, ["completion", "install", "--shell", "zsh"], env=environment)

    assert result.exit_code == 0
    assert (tmp_path / "config/lightning/completions/lightning.zsh").is_file()


def test_unknown_shell_requires_explicit_option(tmp_path):
    environment = _environment(tmp_path, "unsupported")

    result = CliRunner().invoke(main_cli, ["completion", "install"], env=environment)

    assert result.exit_code == 2
    assert "Could not detect a supported shell" in result.output


def test_status_reports_missing_installation(tmp_path):
    environment = _environment(tmp_path, "zsh")

    result = CliRunner().invoke(main_cli, ["completion", "status"], env=environment)

    assert result.exit_code == 1
    assert "Lightning completion is not installed for zsh" in result.output


def test_incomplete_managed_block_is_not_overwritten(tmp_path):
    environment = _environment(tmp_path, "zsh")
    home = Path(environment["HOME"])
    home.mkdir()
    rc_path = home / ".zshrc"
    original = "# >>> lightning completion >>>\n"
    rc_path.write_text(original)

    result = CliRunner().invoke(main_cli, ["completion", "install"], env=environment)

    assert result.exit_code == 1
    assert "Incomplete Lightning completion block" in result.output
    assert rc_path.read_text() == original
    assert not (tmp_path / "config/lightning/completions/lightning.zsh").exists()
