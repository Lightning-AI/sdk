import pytest

from tests.cli.help import assert_help_contains, mock_command_logging

_MMT_COMMANDS = ("run", "list", "inspect", "logs", "ssh", "stop", "delete")


@mock_command_logging
def test_mmt_help() -> None:
    assert_help_contains(
        "lightning mmt --help",
        "Deprecation warning:",
        "Use `lightning job` instead of `lightning mmt`.",
        "Usage: lightning mmt",
        "Multi-node distributed training.",
    )


@mock_command_logging
def test_mmts_list_help_shows_deprecation() -> None:
    # Plural alias shares the wrapped subcommands from the mmt group.
    assert_help_contains(
        "lightning mmts list --help",
        "Deprecation warning:",
        "Use `lightning job` instead of `lightning mmts list`.",
        "Usage: lightning mmts list",
    )


@pytest.mark.parametrize("subcommand", _MMT_COMMANDS)
@mock_command_logging
def test_mmt_deprecation_propagates_to_subcommands(subcommand: str) -> None:
    assert_help_contains(
        f"lightning mmt {subcommand} --help",
        "Deprecation warning:",
        f"Use `lightning job` instead of `lightning mmt {subcommand}`.",
        f"Usage: lightning mmt {subcommand}",
    )
