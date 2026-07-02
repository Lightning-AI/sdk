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
