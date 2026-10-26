import pytest


@pytest.fixture(autouse=True)
def _fixture_disable_version_check(monkeypatch):
    """Silence version-check noise for CLI subprocesses."""
    monkeypatch.setenv("LIGHTNING_DISABLE_VERSION_CHECK", "1")


@pytest.fixture(autouse=True)
def _fixture_no_command_telemetry(monkeypatch):
    """Don't POST CLI command history to the API: unit tests must not need network access."""
    monkeypatch.setattr("lightning_sdk.cli.utils.logging._log_command", lambda *args, **kwargs: None)
