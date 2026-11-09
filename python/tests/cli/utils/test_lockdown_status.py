import json
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from lightning_sdk.cli.utils import lockdown_status
from lightning_sdk.cli.utils.lockdown_status import (
    LOCKDOWN_FLAG,
    RW_FILESYSTEM,
    STUDIOS,
    capability_closed,
    lockdown_flags,
    lockdown_on,
    multi_machine_routes_closed,
)
from lightning_sdk.lightning_cloud import env

_CONFIG = {
    "featureFlags": [
        {"name": LOCKDOWN_FLAG, "value": "true"},
        {"name": "apiLockdownCapabilities", "value": "ro-filesystem, teamspace-lookup,,"},
        {"name": "someOtherFlag", "value": "on"},
    ]
}
_HELD = {LOCKDOWN_FLAG: True, "ro-filesystem": True, "teamspace-lookup": True, "someOtherFlag": False}


@pytest.fixture(autouse=True)
def _fixture_lockdown_on(monkeypatch, tmp_path):
    """Use the real flags, read fresh in each test and cached under ``tmp_path``, instead of the conftest's.

    The caller is signed out unless a test says otherwise, so no credentials are read from the machine.
    """
    monkeypatch.setattr(lockdown_status, "lockdown_flags", lockdown_flags)
    monkeypatch.setattr(lockdown_status, "_flags", lockdown_status._UNREAD)
    monkeypatch.setattr(lockdown_status, "_cache_path", lambda: tmp_path / "lockdown_flags.json")
    monkeypatch.setattr(lockdown_status, "_auth_header", lambda: None)


def _new_process(monkeypatch) -> None:
    monkeypatch.setattr(lockdown_status, "_flags", lockdown_status._UNREAD)


def _config_response(body: object) -> MagicMock:
    response = MagicMock()
    response.json.return_value = body
    return response


def test_reads_the_capabilities_the_caller_holds_from_config() -> None:
    with patch("requests.get", return_value=_config_response(_CONFIG)) as get:
        flags = lockdown_flags()

    assert flags == {LOCKDOWN_FLAG: True, "ro-filesystem": True, "teamspace-lookup": True, "someOtherFlag": False}
    assert get.call_args.args[0] == f"{env.LIGHTNING_CLOUD_URL}/v1/config"


def test_a_capability_missing_from_the_list_is_closed() -> None:
    with patch("requests.get", return_value=_config_response(_CONFIG)):
        assert capability_closed(RW_FILESYSTEM) is True
        assert capability_closed("ro-filesystem") is False


def test_sends_the_callers_credentials(monkeypatch) -> None:
    monkeypatch.setattr(lockdown_status, "_auth_header", lambda: "Bearer token")

    with patch("requests.get", return_value=_config_response(_CONFIG)) as get:
        lockdown_flags()

    assert get.call_args.kwargs["headers"] == {"Authorization": "Bearer token"}


def test_a_signed_out_caller_sends_no_credentials() -> None:
    with patch("requests.get", return_value=_config_response(_CONFIG)) as get:
        lockdown_flags()

    assert get.call_args.kwargs["headers"] == {}


def test_fetches_once_per_process(monkeypatch) -> None:
    with patch("requests.get", return_value=_config_response(_CONFIG)) as get:
        lockdown_flags()
        lockdown_flags()

    assert get.call_count == 1


def test_a_later_process_reads_the_cache_instead_of_fetching(monkeypatch) -> None:
    with patch("requests.get", return_value=_config_response(_CONFIG)):
        lockdown_flags()
    _new_process(monkeypatch)

    with patch("requests.get") as get:
        flags = lockdown_flags()

    assert get.call_count == 0
    assert flags == _HELD


def test_the_cache_is_kept_per_account(monkeypatch) -> None:
    monkeypatch.setattr(lockdown_status, "_auth_header", lambda: "Bearer first")
    with patch("requests.get", return_value=_config_response(_CONFIG)):
        lockdown_flags()
    _new_process(monkeypatch)
    monkeypatch.setattr(lockdown_status, "_auth_header", lambda: "Bearer second")

    with patch(
        "requests.get", return_value=_config_response({"featureFlags": [{"name": LOCKDOWN_FLAG, "value": "true"}]})
    ) as get:
        flags = lockdown_flags()

    assert get.call_count == 1
    assert flags == {LOCKDOWN_FLAG: True}


def test_the_cache_does_not_hold_the_credentials(monkeypatch) -> None:
    monkeypatch.setattr(lockdown_status, "_auth_header", lambda: "Bearer secret-token")
    with patch("requests.get", return_value=_config_response(_CONFIG)):
        lockdown_flags()

    assert "secret-token" not in lockdown_status._cache_path().read_text()


@pytest.mark.parametrize(
    "entry",
    [
        {
            "url": "https://staging.lightning.ai",
            "account": "",
            "flags": {LOCKDOWN_FLAG: True},
            "checked_at": time.time(),
        },
        {
            "url": env.LIGHTNING_CLOUD_URL,
            "account": "",
            "flags": {LOCKDOWN_FLAG: True},
            "checked_at": time.time() - 60 * 60,
        },
        {
            "url": env.LIGHTNING_CLOUD_URL,
            "account": "",
            "flags": {LOCKDOWN_FLAG: True},
            "checked_at": time.time() + 60 * 60,
        },
        {"url": env.LIGHTNING_CLOUD_URL, "account": "", "flags": "nope", "checked_at": time.time()},
        {
            "url": env.LIGHTNING_CLOUD_URL,
            "account": "someone-else",
            "flags": {LOCKDOWN_FLAG: True},
            "checked_at": time.time(),
        },
        # written before the cache was kept per account, with the flags as booleans
        {"url": env.LIGHTNING_CLOUD_URL, "flags": {LOCKDOWN_FLAG: False}, "checked_at": time.time()},
    ],
    ids=["other cloud url", "stale", "from the future", "malformed", "another account", "old format"],
)
def test_ignores_a_cache_entry_it_cannot_use(entry: dict) -> None:
    lockdown_status._cache_path().write_text(json.dumps(entry))

    with patch("requests.get", return_value=_config_response(_CONFIG)) as get:
        flags = lockdown_flags()

    assert get.call_count == 1
    assert flags == _HELD


@pytest.mark.parametrize(
    "fetch",
    [
        MagicMock(side_effect=requests.ConnectionError("offline")),
        MagicMock(return_value=MagicMock(raise_for_status=MagicMock(side_effect=requests.HTTPError("403")))),
        MagicMock(return_value=MagicMock(json=MagicMock(side_effect=ValueError("not json")))),
        MagicMock(return_value=_config_response({"featureFlags": [{"value": "true"}]})),
    ],
    ids=["offline", "refused", "not json", "flag without a name"],
)
def test_flags_it_cannot_read_are_none_and_not_cached(monkeypatch, fetch: MagicMock) -> None:
    with patch("requests.get", fetch):
        assert lockdown_flags() is None

    assert not lockdown_status._cache_path().exists()


@pytest.mark.parametrize(
    ("flags", "on", "rw_filesystem_closed", "mmt_closed"),
    [
        ({LOCKDOWN_FLAG: True}, True, True, True),
        ({LOCKDOWN_FLAG: True, RW_FILESYSTEM: True}, True, False, True),
        # holding other capabilities doesn't open this one, or the multi-machine routes
        ({LOCKDOWN_FLAG: True, STUDIOS: True}, True, True, True),
        ({LOCKDOWN_FLAG: False}, False, False, False),
        # a control plane that doesn't send apiLockdown is read as locked down, as the CLI was before the flags
        ({}, True, True, True),
        # unreadable: the server enforces the lockdown, so only the commands it never opens stay refused
        (None, True, False, False),
    ],
)
def test_lockdown_on_and_capability_closed(
    monkeypatch, flags, on: bool, rw_filesystem_closed: bool, mmt_closed: bool
) -> None:
    monkeypatch.setattr(lockdown_status, "lockdown_flags", lambda: flags)

    assert lockdown_on() is on
    assert capability_closed(RW_FILESYSTEM) is rw_filesystem_closed
    assert multi_machine_routes_closed() is mmt_closed
