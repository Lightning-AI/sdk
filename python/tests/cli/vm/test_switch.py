from tests.cli.help import assert_help_contains, command_text


def test_switch_vm():
    result_text = command_text("lightning vm switch --help")

    assert "Usage: lightning vm switch [OPTIONS]" in result_text
    assert "Switch a VM to a different machine type." in result_text
    assert "--name           TEXT" in result_text
    assert "--teamspace      TEXT" in result_text
    assert "--machine" in result_text
    assert "--interruptible" in result_text


def test_vms_switch_help() -> None:
    assert_help_contains(
        "lightning vms switch --help", "Usage: lightning vms switch", "Switch a VM to a different machine type."
    )
