import pytest


@pytest.fixture(autouse=True)
def _fixture_reset_auth(monkeypatch):
    """Reset the auth state and silence version-check noise for CLI subprocesses."""
    from lightning_sdk.lightning_cloud.login import Auth

    monkeypatch.setenv("LIGHTNING_DISABLE_VERSION_CHECK", "1")

    auth = Auth()
    auth.clear()
    yield
    auth.clear()
