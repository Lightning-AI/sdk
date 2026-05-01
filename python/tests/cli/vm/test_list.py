from tests.cli.help import assert_help_contains, command_text


def test_list_vm():
    result_text = command_text("lightning vm list --help")

    assert "Usage: lightning vm list [OPTIONS]" in result_text
    assert "List VMs in a teamspace." in result_text
    assert "--teamspace TEXT" in result_text
    assert "--all" in result_text
    assert "--sort-by" in result_text


def test_vms_list_help() -> None:
    assert_help_contains("lightning vms list --help", "Usage: lightning vms list", "List VMs in a teamspace.")
