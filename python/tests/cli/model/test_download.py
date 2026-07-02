from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_model_download_help() -> None:
    assert_help_contains(
        "lightning model download --help", "Usage: lightning model download", "Download a model from a teamspace."
    )


@mock_command_logging
def test_models_download_help() -> None:
    assert_help_contains(
        "lightning models download --help", "Usage: lightning models download", "Download a model from a teamspace."
    )


@mock_command_logging
def test_download_model_legacy_help() -> None:
    assert_help_contains(
        "lightning download model --help",
        "Deprecation warning:",
        "Use `lightning model download` instead of `lightning download model`.",
        "Usage: lightning download model [OPTIONS] NAME",
    )
