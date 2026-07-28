from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_mmt_delete_help() -> None:
    assert_help_contains("lightning mmt delete --help", "Usage: lightning mmt delete", "Delete a multi-machine job.")


@mock_command_logging
def test_mmts_delete_help() -> None:
    assert_help_contains("lightning mmts delete --help", "Usage: lightning mmts delete", "Delete a multi-machine job.")


@mock_command_logging
def test_delete_mmt_legacy_help() -> None:
    assert_help_contains(
        "lightning delete mmt --help",
        "Deprecation warning:",
        "Use `lightning mmt delete` instead of `lightning delete mmt`.",
        "Usage: lightning delete mmt [OPTIONS] NAME",
    )


@mock_command_logging
def test_mmt_delete_resolves_exact_name() -> None:
    from lightning_sdk.cli.mmt.delete import delete_mmt

    teamspace = MagicMock()
    mmt = MagicMock()
    mmt.name = "distributed"
    with patch("lightning_sdk.cli.mmt.delete.resolve_teamspace", return_value=teamspace) as resolve_teamspace, patch(
        "lightning_sdk.cli.mmt.delete.resolve_mmt", return_value=mmt
    ) as resolve_mmt:
        result = CliRunner().invoke(delete_mmt, ["distributed", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0
    resolve_teamspace.assert_called_once_with("org/teamspace")
    resolve_mmt.assert_called_once_with("distributed", teamspace)
    mmt.delete.assert_called_once_with()
