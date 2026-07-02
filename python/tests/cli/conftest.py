import pytest


@pytest.fixture(autouse=True)
def _fixture_disable_version_check(monkeypatch):
    """Silence version-check noise for CLI subprocesses."""
    monkeypatch.setenv("LIGHTNING_DISABLE_VERSION_CHECK", "1")
