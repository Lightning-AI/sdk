from tests.cli.help import command_text, mock_command_logging


@mock_command_logging
def test_studio_help():
    result_text = command_text("lightning studio --help")

    assert "Usage: lightning studio [OPTIONS] COMMAND [ARGS]..." in result_text
    assert "connect             Connect to a Studio." in result_text
    assert "cp                  Copy a Studio file." in result_text
    assert "create              Create a new Studio." in result_text
    assert "delete              Delete a Studio." in result_text
    assert "list                List Studios in a teamspace." in result_text
    assert "ls                  List contents of a directory in Studio." in result_text
    assert "open                Open a local file or folder in a Lightning Studio." in result_text
    assert "rm                  Remove a Studio file or directory." in result_text
    assert "ssh                 SSH into a Studio." in result_text
    assert "start               Start a Studio" in result_text
    assert "stop                Stop a Studio." in result_text
    assert "switch              Switch a Studio to a different machine type." in result_text


@mock_command_logging
def test_studios_help():
    result_text = command_text("lightning studios --help")

    assert "Usage: lightning studios [OPTIONS] COMMAND [ARGS]..." in result_text
    assert "Persistent GPU dev workspaces." in result_text
