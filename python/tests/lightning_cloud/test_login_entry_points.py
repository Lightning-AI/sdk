import pytest

from lightning_sdk.lightning_cloud import cli_login
from lightning_sdk.lightning_cloud.credentials import CredentialSource, start_login
from lightning_sdk.lightning_cloud.login import Auth

_ENTRY_POINTS = {
    "start_login": start_login,
    "Auth._run_server": lambda: Auth()._run_server(),
    "Auth.authenticate": lambda: Auth().authenticate(),
    "CredentialSource.header": lambda: CredentialSource().header(),
}


@pytest.mark.parametrize("entry", list(_ENTRY_POINTS))
@pytest.mark.parametrize("switch", [None, "0", "1"])
def test_every_entry_point_starts_the_new_login_whatever_the_old_switch_says(
    platform, browser, monkeypatch, entry, switch
):
    if switch is not None:
        monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", switch)

    _ENTRY_POINTS[entry]()
    browser.finish()

    assert (len(platform.authorizations), platform.sign_ins) == (1, [])
    assert cli_login.current_login() is not None
    assert not Auth.secrets_file.exists()
