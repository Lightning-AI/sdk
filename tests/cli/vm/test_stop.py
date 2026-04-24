from tests.cli.help import assert_help_contains, command_text


def test_stop_vm():
    result_text = command_text("lightning vm stop --help")

    assert "Usage: lightning vm stop [OPTIONS]" in result_text
    assert "Stop a VM." in result_text
    assert "--name TEXT" in result_text
    assert "--teamspace TEXT" in result_text


def test_vms_stop_help() -> None:
    assert_help_contains("lightning vms stop --help", "Usage: lightning vms stop", "Stop a VM.")
