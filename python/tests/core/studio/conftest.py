from unittest import mock

import pytest

# Identity / location env vars that leak from the host studio into the test process and would
# otherwise make Studio construction resolve a real user/teamspace (and hit the network).
_AMBIENT_ENV_VARS = (
    "LIGHTNING_USERNAME",
    "LIGHTNING_USER_ID",
    "LIGHTNING_ORG",
    "LIGHTNING_TEAMSPACE",
    "LIGHTNING_CLOUD_SPACE_ID",
    "LIGHTNING_CLOUD_PROJECT_ID",
)


@pytest.fixture(autouse=True)
def _offline_studio_env(monkeypatch):
    """Make Studio construction hermetic and offline for these unit tests.

    Drops ambient identity/location env vars (so resolution uses only what each test sets), and
    stubs the teamspace access check, which otherwise reaches the backend and fails without auth.
    """
    for var in _AMBIENT_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    with (
        mock.patch("lightning_sdk.studio.raise_access_error_if_not_allowed", return_value=None),
        mock.patch("lightning_sdk.api.studio_api.StudioApi.start_keeping_alive", autospec=True),
    ):
        yield
