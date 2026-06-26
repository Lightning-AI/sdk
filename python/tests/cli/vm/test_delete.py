from tests.cli.help import assert_help_contains, command_text


def test_delete_vm():
    result_text = command_text("lightning vm delete --help")

    assert "Usage: lightning vm delete [OPTIONS]" in result_text
    assert "Delete a VM." in result_text
    assert "--name       TEXT" in result_text
    assert "--teamspace  TEXT" in result_text


def test_vms_delete_help() -> None:
    assert_help_contains("lightning vms delete --help", "Usage: lightning vms delete", "Delete a VM.")
