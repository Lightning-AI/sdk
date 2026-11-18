import re
import threading

import pytest

from lightning_sdk.lightning_cloud import cli_login, env, service_account
from lightning_sdk.lightning_cloud.cli_login import LoginError
from lightning_sdk.lightning_cloud.credentials import Credential, CredentialKind, CredentialSource
from lightning_sdk.lightning_cloud.rest_client import LightningClient

_HOUR = 3600


def _exactly(message):
    return f"^{re.escape(message)}$"


@pytest.fixture()
def key(platform, monkeypatch):
    issued = platform.add_service_account_key("sa-1")
    monkeypatch.setenv("LIGHTNING_API_KEY", issued)
    return issued


def test_the_key_is_exchanged_once_and_only_the_token_reaches_the_api(platform, key):
    credential = CredentialSource().resolve()
    assert credential.kind is CredentialKind.SERVICE_ACCOUNT
    assert credential.token.startswith("lit_ua_")
    assert key not in repr(credential)

    assert LightningClient().auth_service_get_user().id == "sa-1"
    assert LightningClient().auth_service_get_user().id == "sa-1"

    assert platform.key_exchanges() == [{"grant_type": "client_credentials", "client_secret": key}]
    assert platform.authorizations_sent("/v1/auth/user") == [credential.header, credential.header]


def test_the_token_file_and_environment_token_win_and_the_key_beats_a_login(
    platform, browser, key, monkeypatch, tmp_path
):
    made = cli_login.login()
    browser.finish()
    token_file = tmp_path / "token"
    token_file.write_text("lit_w_file")
    monkeypatch.setenv(env.LIGHTNING_AUTH_TOKEN_FILE, str(token_file))
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN", "sess_env")
    source = CredentialSource()

    assert source.resolve() == Credential(CredentialKind.TOKEN_FILE, "lit_w_file")
    token_file.unlink()
    assert source.resolve() == Credential(CredentialKind.ENV_TOKEN, "sess_env")
    assert platform.key_exchanges() == [], "a key that isn't used isn't exchanged"

    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN")
    assert source.resolve().kind is CredentialKind.SERVICE_ACCOUNT
    monkeypatch.setenv("LIGHTNING_API_KEY", "  ")
    assert source.resolve() == Credential(CredentialKind.LOGIN, made.access_token)


def test_the_token_is_reused_until_five_minutes_before_it_expires(platform, key, clock):
    first = service_account.token()
    clock.advance(_HOUR - 301)
    assert service_account.token() == first
    assert len(platform.key_exchanges()) == 1

    clock.advance(2)
    second = service_account.token()
    assert second != first
    assert len(platform.key_exchanges()) == 2


def test_a_rejected_token_is_exchanged_again(platform, key):
    source = CredentialSource()
    header = source.header()
    platform.revoke_access_token(header[len("Bearer ") :])

    assert source.refresh(header) is True
    assert source.header() != header
    assert len(platform.key_exchanges()) == 2


def test_requests_retry_once_with_a_fresh_token(platform, key):
    assert LightningClient().auth_service_get_user().id == "sa-1"
    platform.revoke_access_token(platform.authorizations_sent("/v1/auth/user")[0][len("Bearer ") :])

    assert LightningClient().auth_service_get_user().id == "sa-1"
    assert len(platform.key_exchanges()) == 2


def test_a_revoked_key_is_named_with_what_to_do(platform, key):
    source = CredentialSource()
    header = source.header()
    platform.revoke_service_account_key(key)
    refusal = (
        "Lightning refused the key in LIGHTNING_API_KEY: service account key revoked. "
        "Use a current key, or unset LIGHTNING_API_KEY to use your login."
    )

    with pytest.raises(LoginError, match=_exactly(refusal)):
        source.refresh(header)
    # A request finds out when its cached token is refused, and says why.
    with pytest.raises(LoginError, match=_exactly(refusal)):
        LightningClient().auth_service_get_user()


def test_any_value_is_exchanged_and_one_that_isnt_a_key_is_refused_without_a_browser(platform, monkeypatch):
    # A user API key from before service accounts, left exported.
    monkeypatch.setenv("LIGHTNING_API_KEY", "legacy-user-key")

    with pytest.raises(LoginError, match="invalid service account key") as refused:
        CredentialSource().header()
    assert "legacy-user-key" not in str(refused.value)
    assert platform.key_exchanges() == [{"grant_type": "client_credentials", "client_secret": "legacy-user-key"}]
    assert platform.authorizations_sent("/v1/auth/user") == []


def test_a_deployment_without_the_grant_says_so(platform, key):
    platform.key_exchange_answer = (400, {"error": "unsupported_grant_type"})

    with pytest.raises(
        LoginError,
        match=_exactly(
            f"{platform.url} doesn't accept service-account keys. Unset LIGHTNING_API_KEY to use your login."
        ),
    ):
        service_account.token()


def test_an_outage_keeps_a_token_with_time_left_and_fails_once_it_expires(platform, key, clock):
    first = service_account.token()
    clock.advance(_HOUR - 100)
    platform.key_exchange_answer = (503, {})

    assert service_account.token() == first

    clock.advance(200)
    with pytest.raises(
        LoginError, match=_exactly("Lightning answered the LIGHTNING_API_KEY exchange with 503. Try again shortly.")
    ):
        service_account.token()


def test_an_unreachable_server_is_named(monkeypatch):
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("LIGHTNING_API_KEY", "lit_sa_any")

    with pytest.raises(LoginError, match="Couldn't reach http://127.0.0.1:9 to exchange LIGHTNING_API_KEY"):
        service_account.token()


def test_an_answer_without_a_usable_token_is_refused(platform, key):
    platform.key_exchange_answer = (200, {"access_token": "lit_ua_x", "expires_in": True})

    with pytest.raises(LoginError, match="without a usable token"):
        service_account.token()


def test_a_new_key_in_the_same_process_is_exchanged(platform, key, monkeypatch):
    first = service_account.token()
    monkeypatch.setenv("LIGHTNING_API_KEY", platform.add_service_account_key("sa-2"))

    second = service_account.token()

    assert second != first
    assert platform.user_of(second) == "sa-2"


def test_threads_starting_together_share_one_exchange(platform, key):
    start = threading.Barrier(8)
    tokens = []

    def request():
        start.wait()
        tokens.append(CredentialSource().header())

    threads = [threading.Thread(target=request) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(set(tokens)) == 1
    assert len(platform.key_exchanges()) == 1
