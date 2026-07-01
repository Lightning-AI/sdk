from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_container_upload_help() -> None:
    assert_help_contains(
        "lightning container upload --help",
        "Usage: lightning container upload",
        "Upload a container to Lightning AI's container registry.",
    )


@mock_command_logging
def test_containers_upload_help() -> None:
    assert_help_contains(
        "lightning containers upload --help",
        "Usage: lightning containers upload",
        "Upload a container to Lightning AI's container registry.",
    )


@mock_command_logging
def test_upload_help() -> None:
    text = assert_help_contains(
        "lightning upload --help",
        "`lightning upload` has moved to noun-first commands:",
        "container -> lightning container upload",
        "file -> lightning file upload",
        "folder -> lightning folder upload",
        "model -> lightning model upload",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_upload_container_legacy_help() -> None:
    assert_help_contains(
        "lightning upload container --help",
        "Deprecation warning:",
        "Use `lightning container upload` instead of `lightning upload container`.",
        "Usage: lightning upload container [OPTIONS] CONTAINER",
    )
