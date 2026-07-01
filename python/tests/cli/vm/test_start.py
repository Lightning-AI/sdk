from tests.cli.help import assert_help_contains, command_text


def test_start_vm():
    result_text = command_text("lightning vm start --help")

    assert "Usage: lightning vm start [OPTIONS]" in result_text
    assert "Start a VM." in result_text
    assert "--name" in result_text
    assert "--teamspace" in result_text
    assert "--create" in result_text
    assert "--machine" in result_text
    assert "--interruptible" in result_text
    assert "--cloud" in result_text
    assert "--cloud-provider" not in result_text
    assert "--cloud-account" not in result_text


def test_vms_start_help() -> None:
    assert_help_contains("lightning vms start --help", "Usage: lightning vms start", "Start a VM.")
