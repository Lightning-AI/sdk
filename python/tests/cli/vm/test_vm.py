from tests.cli.help import command_text


def test_vm_help():
    result_text = command_text("lightning vm --help")

    assert "Usage: lightning vm [OPTIONS] COMMAND [ARGS]..." in result_text
    assert "Bare VMs with SSH access." in result_text
    assert "create              Create a new VM." in result_text
    assert "delete              Delete a VM." in result_text
    assert "list                List VMs in a teamspace." in result_text
    assert "ssh                 SSH into a VM" in result_text
    assert "start               Start a VM." in result_text
    assert "stop                Stop a VM." in result_text
    assert "switch              Switch a VM to a different machine type." in result_text
