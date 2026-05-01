from tests.cli.help import assert_help_contains


def test_machine_help() -> None:
    assert_help_contains("lightning machine --help", "Usage: lightning machine", "Manage Lightning AI machine types.")


def test_machines_help() -> None:
    assert_help_contains("lightning machines --help", "Usage: lightning machines", "Manage Lightning AI machine types.")
