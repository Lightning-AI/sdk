from tests.cli.help import assert_help_contains


def test_container_download_help() -> None:
    assert_help_contains(
        "lightning container download --help",
        "Usage: lightning container download",
        "Download a docker container from a teamspace.",
    )


def test_containers_download_help() -> None:
    assert_help_contains(
        "lightning containers download --help",
        "Usage: lightning containers download",
        "Download a docker container from a teamspace.",
    )


def test_download_help() -> None:
    text = assert_help_contains(
        "lightning download --help",
        "`lightning download` has moved to noun-first commands:",
        "container -> lightning container download",
        "file -> lightning file download",
        "folder -> lightning folder download",
        "model -> lightning model download",
    )
    assert "Deprecation warning:" not in text


def test_download_container_legacy_help() -> None:
    assert_help_contains(
        "lightning download container --help",
        "Deprecation warning:",
        "Use `lightning container download` instead of `lightning download container`.",
        "Usage: lightning download container [OPTIONS] CONTAINER",
    )
