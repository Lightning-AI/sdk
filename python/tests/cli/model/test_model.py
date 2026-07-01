from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_model_help() -> None:
    assert_help_contains("lightning model --help", "Usage: lightning model", "Register and version models.")


@mock_command_logging
def test_models_help() -> None:
    assert_help_contains("lightning models --help", "Usage: lightning models", "Register and version models.")
