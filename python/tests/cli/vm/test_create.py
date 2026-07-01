from tests.cli.help import assert_help_contains, command_text, mock_command_logging


@mock_command_logging
def test_create_vm():
    result_text = command_text("lightning vm create --help")

    assert "Usage: lightning vm create [OPTIONS]" in result_text
    assert "Create a new VM." in result_text
    assert "--name" in result_text
    assert "--teamspace" in result_text
    assert "--cloud" in result_text
    assert "--cloud-provider" not in result_text
    assert "--cloud-account" not in result_text


@mock_command_logging
def test_vms_create_help() -> None:
    assert_help_contains("lightning vms create --help", "Usage: lightning vms create", "Create a new VM.")
