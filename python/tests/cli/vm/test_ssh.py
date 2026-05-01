from tests.cli.help import assert_help_contains, command_text


def test_ssh_vm():
    result_text = command_text("lightning vm ssh --help")

    assert "Usage: lightning vm ssh [OPTIONS]" in result_text
    assert "SSH into a VM." in result_text
    assert "--name TEXT" in result_text
    assert "--teamspace TEXT" in result_text
    assert "-o, --option TEXT" in result_text


def test_vms_ssh_help() -> None:
    assert_help_contains("lightning vms ssh --help", "Usage: lightning vms ssh", "SSH into a VM.")
