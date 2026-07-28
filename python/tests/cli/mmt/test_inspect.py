from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_mmt_inspect_help() -> None:
    assert_help_contains(
        "lightning mmt inspect --help",
        "Usage: lightning mmt inspect",
        "Inspect a multi-machine job for further details as JSON.",
        "configured default teamspace",
    )


@mock_command_logging
def test_mmts_inspect_help() -> None:
    assert_help_contains(
        "lightning mmts inspect --help",
        "Usage: lightning mmts inspect",
        "Inspect a multi-machine job for further details as JSON.",
    )


@mock_command_logging
def test_inspect_mmt_legacy_help() -> None:
    assert_help_contains(
        "lightning inspect mmt --help",
        "Deprecation warning:",
        "Use `lightning mmt inspect` instead of `lightning inspect mmt`.",
        "Usage: lightning inspect mmt [OPTIONS]",
    )


@mock_command_logging
def test_mmt_inspect_uses_name_option() -> None:
    from lightning_sdk.cli.mmt.inspect import inspect_mmt

    teamspace = MagicMock()
    mmt = MagicMock()
    mmt.json.return_value = '{"name":"distributed"}'
    with patch("lightning_sdk.cli.mmt.inspect.resolve_teamspace", return_value=teamspace) as resolve_teamspace, patch(
        "lightning_sdk.cli.mmt.inspect.resolve_mmt", return_value=mmt
    ) as resolve_mmt:
        result = CliRunner().invoke(inspect_mmt, ["--name", "distributed", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0
    resolve_teamspace.assert_called_once_with("org/teamspace")
    resolve_mmt.assert_called_once_with("distributed", teamspace)
    mmt.json.assert_called_once_with()


@mock_command_logging
def test_mmt_inspect_requires_name_without_listing_resources() -> None:
    from lightning_sdk.cli.mmt.inspect import inspect_mmt

    teamspace = MagicMock()
    with patch("lightning_sdk.cli.mmt.inspect.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.utils.resource_resolution.MMT"
    ) as mmt:
        result = CliRunner().invoke(inspect_mmt)

    assert result.exit_code != 0
    assert "Missing multi-machine job name. Pass JOB." in result.output
    mmt.assert_not_called()
    assert teamspace.mock_calls == []
