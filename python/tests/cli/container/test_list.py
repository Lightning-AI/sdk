from unittest.mock import MagicMock, patch

from lightning_sdk.cli.legacy.list import containers
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_container_list_help() -> None:
    assert_help_contains(
        "lightning container list --help",
        "Usage: lightning container list",
        "Display the list of available containers.",
    )


@mock_command_logging
def test_containers_list_help() -> None:
    assert_help_contains(
        "lightning containers list --help",
        "Usage: lightning containers list",
        "Display the list of available containers.",
    )


@mock_command_logging
def test_list_help() -> None:
    text = assert_help_contains(
        "lightning list --help",
        "`lightning list` has moved to noun-first commands:",
        "containers -> lightning container list",
        "jobs -> lightning job list",
        "machines -> lightning machine list",
        "mmts -> lightning mmt list",
        "studios -> lightning studio list",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_list_containers_legacy_help() -> None:
    assert_help_contains(
        "lightning list containers --help",
        "Deprecation warning:",
        "Use `lightning container list` instead of `lightning list containers`.",
        "Usage: lightning list containers [OPTIONS]",
    )


@patch("lightning_sdk.cli.legacy.list.resolve_cluster", return_value="resolved-account")
@patch("lightning_sdk.cli.legacy.list.resolve_teamspace")
@patch("lightning_sdk.cli.legacy.list.LitContainer")
def test_list_containers_resolves_explicit_cloud_account(
    lit_container: MagicMock,
    resolve_teamspace: MagicMock,
    resolve_cluster: MagicMock,
) -> None:
    teamspace = MagicMock()
    teamspace.name = "teamspace"
    teamspace.owner.name = "owner"
    resolve_teamspace.return_value = teamspace
    lit_container.return_value.list_containers.return_value = []

    containers.callback(teamspace="owner/teamspace", cloud_account="account")

    lit_container.return_value.list_containers.assert_called_once_with(
        teamspace="teamspace",
        org="owner",
        cloud_account="resolved-account",
    )
    resolve_cluster.assert_called_once_with(teamspace, "account", "--cloud-account")
