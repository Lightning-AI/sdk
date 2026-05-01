from tests.cli.help import assert_help_contains


def test_model_help() -> None:
    assert_help_contains("lightning model --help", "Usage: lightning model", "Manage Lightning AI Models.")


def test_models_help() -> None:
    assert_help_contains("lightning models --help", "Usage: lightning models", "Manage Lightning AI Models.")
