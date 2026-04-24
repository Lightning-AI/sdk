from tests.cli.help import assert_help_contains


def test_container_delete_help() -> None:
    assert_help_contains(
        "lightning container delete --help", "Usage: lightning container delete", "Delete the docker container NAME."
    )


def test_containers_delete_help() -> None:
    assert_help_contains(
        "lightning containers delete --help", "Usage: lightning containers delete", "Delete the docker container NAME."
    )


def test_delete_container_legacy_help() -> None:
    assert_help_contains(
        "lightning delete container --help",
        "Deprecation warning:",
        "Use `lightning container delete` instead of `lightning delete container`.",
        "Usage: lightning delete container [OPTIONS] NAME",
    )
