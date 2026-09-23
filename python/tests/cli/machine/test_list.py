from unittest import mock

from lightning_sdk.machine import Machine
from tests.cli.help import assert_help_contains, command_text, mock_command_logging

_HELP_SUMMARY = "Display the machines you can start in your cloud account."


def mock_account_machines(machines):
    """Stand in for the cloud account lookup so the CLI does not hit the network."""
    return mock.patch(
        "lightning_sdk.cli.machine.list._account_machines",
        autospec=True,
        return_value=(machines, "lightning-public-prod"),
    )


@mock_command_logging
def test_machine_list_help() -> None:
    assert_help_contains("lightning machine list --help", "Usage: lightning machine list", _HELP_SUMMARY)


@mock_command_logging
def test_machines_list_help() -> None:
    assert_help_contains("lightning machines list --help", "Usage: lightning machines list", _HELP_SUMMARY)


@mock_command_logging
def test_list_machines_legacy_help() -> None:
    assert_help_contains(
        "lightning list machines --help",
        "Deprecation warning:",
        "Use `lightning machine list` instead of `lightning list machines`.",
        "Usage: lightning list machines [OPTIONS]",
    )


@mock_command_logging
def test_machines_output_lists_only_what_the_account_offers() -> None:
    # The cloud account offers 8x H200 but no single-GPU H200, so only the 8x variant may show up:
    # listing a machine the account cannot start is what sent users at an unavailable SKU.
    with mock_account_machines([Machine.CPU, Machine.H200_X_8]):
        result_text = command_text("lightning machine list")

    assert "H200_X_8" in result_text
    assert "H200_X_4" not in result_text
    assert "\nH200 " not in result_text
    assert "lightning-public-prod" in result_text


@mock_command_logging
def test_machines_output_shows_count_and_family() -> None:
    with mock_account_machines([Machine.H200_X_8]):
        result_text = command_text("lightning machine list")

    assert "H200" in result_text
    assert "8" in result_text


@mock_command_logging
def test_machines_catalog_output() -> None:
    result_text = command_text("lightning machine list --catalog")

    # --catalog is the old behaviour: every machine the SDK knows about, account or not.
    for name in ("A100", "B200_X_8", "CPU_SMALL", "DATA_PREP_ULTRA", "H200", "H200_X_4", "T4_SMALL"):
        assert name in result_text
    assert "SDK catalog" in result_text


@mock_command_logging
def test_machines_json_output() -> None:
    import json

    with mock_account_machines([Machine.H200_X_8]):
        result_text = command_text("lightning machine list --json")

    assert json.loads(result_text) == [
        {"name": "H200_X_8", "family": "H200", "count": 8, "cloud_account": "lightning-public-prod"}
    ]
