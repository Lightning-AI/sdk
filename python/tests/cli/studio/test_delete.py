from tests.cli.help import assert_help_contains, command_text, mock_command_logging


def test_delete_invalid_studio_does_not_confirm_or_delete() -> None:
    """An unresolved studio exits before the destructive confirmation and delete call."""
    from unittest.mock import MagicMock, patch

    import rich_click as click
    from click.testing import CliRunner

    from lightning_sdk.cli.studio.delete import delete_studio

    confirm = MagicMock()
    with patch(
        "lightning_sdk.cli.studio.delete.resolve_teamspace",
        return_value=MagicMock(),
    ), patch(
        "lightning_sdk.cli.studio.delete.resolve_studio",
        side_effect=click.UsageError("Unknown studio"),
    ), patch("lightning_sdk.cli.studio.delete.click.confirm", confirm):
        result = CliRunner().invoke(delete_studio, ["--name", "missing"])

    assert result.exit_code != 0
    confirm.assert_not_called()


@mock_command_logging
def test_delete_studio():
    result_text = command_text("lightning studio delete --help")

    assert "Usage: lightning studio delete [OPTIONS]" in result_text
    assert "Delete a Studio." in result_text
    assert "--name       TEXT" in result_text
    assert "--teamspace  TEXT" in result_text


@mock_command_logging
def test_studios_delete_help() -> None:
    assert_help_contains("lightning studios delete --help", "Usage: lightning studios delete", "Delete a Studio.")


@mock_command_logging
def test_delete_studio_legacy_help() -> None:
    assert_help_contains(
        "lightning delete studio --help",
        "Deprecation warning:",
        "Use `lightning studio delete` instead of `lightning delete studio`.",
        "Usage: lightning delete studio [OPTIONS]",
    )
