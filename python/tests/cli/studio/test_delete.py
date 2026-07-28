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


def test_studio_delete_requires_yes_without_prompting_or_deleting() -> None:
    """Missing ``--yes`` must stop a resolved studio deletion before its side effect."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.delete import delete_studio

    studio = MagicMock()
    studio._cls_name = "Studio"
    studio.name = "dev"
    studio.teamspace.owner.name = "acme"
    studio.teamspace.name = "platform"
    with patch("lightning_sdk.cli.studio.delete.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.studio.delete.resolve_studio", return_value=studio
    ), patch(
        "lightning_sdk.cli.studio.delete.click.confirm", side_effect=AssertionError("must not prompt")
    ):
        result = CliRunner().invoke(delete_studio, ["--name", "dev"])

    assert result.exit_code != 0
    assert "--yes" in result.output
    studio.delete.assert_not_called()


def test_studio_delete_yes_deletes_without_prompting() -> None:
    """``--yes`` authorizes studio deletion without reading confirmation input."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.delete import delete_studio

    studio = MagicMock()
    studio._cls_name = "Studio"
    studio.name = "dev"
    studio.teamspace.owner.name = "acme"
    studio.teamspace.name = "platform"
    with patch("lightning_sdk.cli.studio.delete.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.studio.delete.resolve_studio", return_value=studio
    ), patch(
        "lightning_sdk.cli.studio.delete.click.confirm", side_effect=AssertionError("must not prompt")
    ):
        result = CliRunner().invoke(delete_studio, ["--name", "dev", "--yes"], input="no input")

    assert result.exit_code == 0, result.output
    studio.delete.assert_called_once_with()


@mock_command_logging
def test_delete_studio():
    result_text = command_text("lightning studio delete --help")

    assert "Usage: lightning studio delete [OPTIONS]" in result_text
    assert "Delete a Studio." in result_text
    assert "--name" in result_text
    assert "--teamspace" in result_text
    assert "--yes" in result_text


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
