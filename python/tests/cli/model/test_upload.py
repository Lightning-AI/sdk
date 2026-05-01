from tests.cli.help import assert_help_contains


def test_model_upload_help() -> None:
    assert_help_contains(
        "lightning model upload --help", "Usage: lightning model upload", "Upload a model to a teamspace."
    )


def test_models_upload_help() -> None:
    assert_help_contains(
        "lightning models upload --help", "Usage: lightning models upload", "Upload a model to a teamspace."
    )


def test_upload_model_legacy_help() -> None:
    assert_help_contains(
        "lightning upload model --help",
        "Deprecation warning:",
        "Use `lightning model upload` instead of `lightning upload model`.",
        "Usage: lightning upload model [OPTIONS] NAME",
    )
