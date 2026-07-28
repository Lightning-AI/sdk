from tests.cli.help import assert_help_contains, mock_command_logging


def test_generate_uses_deterministic_resolvers() -> None:
    """Generating SSH config resolves the requested studio without a menu."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.ssh.generate import generate_ssh

    teamspace = MagicMock()
    studio = MagicMock()
    studio._studio.id = "studio-id"
    studio.name = "dev"
    with patch(
        "lightning_sdk.cli.ssh.generate.resolve_teamspace",
        return_value=teamspace,
    ) as resolve_teamspace, patch(
        "lightning_sdk.cli.ssh.generate.resolve_studio",
        return_value=studio,
    ) as resolve_studio:
        result = CliRunner().invoke(generate_ssh, ["--name", "dev"])

    assert result.exit_code == 0
    assert "Host dev" in result.output
    resolve_teamspace.assert_called_once_with(None)
    resolve_studio.assert_called_once_with("dev", teamspace)


@mock_command_logging
def test_ssh_generate_help() -> None:
    assert_help_contains(
        "lightning ssh generate --help", "Usage: lightning ssh generate", "Get SSH config entry for a studio."
    )


@mock_command_logging
def test_generate_help() -> None:
    text = assert_help_contains(
        "lightning generate --help",
        "`lightning generate` has moved to noun-first commands:",
        "ssh -> lightning ssh generate",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_generate_ssh_legacy_help() -> None:
    assert_help_contains(
        "lightning generate ssh --help",
        "Deprecation warning:",
        "Use `lightning ssh generate` instead of `lightning generate ssh`.",
        "Usage: lightning generate ssh [OPTIONS]",
    )
