from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_mmt_stop_help() -> None:
    assert_help_contains("lightning mmt stop --help", "Usage: lightning mmt stop", "Stop a multi-machine job.")


@mock_command_logging
def test_mmts_stop_help() -> None:
    assert_help_contains("lightning mmts stop --help", "Usage: lightning mmts stop", "Stop a multi-machine job.")


@mock_command_logging
def test_stop_mmt_legacy_help() -> None:
    assert_help_contains(
        "lightning stop mmt --help",
        "Deprecation warning:",
        "Use `lightning mmt stop` instead of `lightning stop mmt`.",
        "Usage: lightning stop mmt [OPTIONS] NAME",
    )


@mock_command_logging
def test_mmt_stop_resolves_exact_name() -> None:
    from lightning_sdk.cli.mmt.stop import stop_mmt

    teamspace = MagicMock()
    mmt = MagicMock()
    mmt.name = "distributed"
    with patch("lightning_sdk.cli.mmt.stop.resolve_teamspace", return_value=teamspace) as resolve_teamspace, patch(
        "lightning_sdk.cli.mmt.stop.resolve_mmt", return_value=mmt
    ) as resolve_mmt:
        result = CliRunner().invoke(stop_mmt, ["distributed", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0
    resolve_teamspace.assert_called_once_with("org/teamspace")
    resolve_mmt.assert_called_once_with("distributed", teamspace)
    mmt.stop.assert_called_once_with()
