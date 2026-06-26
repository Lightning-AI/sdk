from tests.cli.help import assert_help_contains


def test_machine_help() -> None:
    assert_help_contains("lightning machine --help", "Usage: lightning machine", "Browse GPU and CPU machine types.")


def test_machines_help() -> None:
    assert_help_contains("lightning machines --help", "Usage: lightning machines", "Browse GPU and CPU machine types.")
