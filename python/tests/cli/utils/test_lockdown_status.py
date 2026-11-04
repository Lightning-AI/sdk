import json
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from lightning_sdk.cli.utils import lockdown_status
from lightning_sdk.cli.utils.lockdown_status import (
    LOCKDOWN_FLAG,
    UPLOADS_FLAG,
    capability_closed,
    lockdown_flags,
    lockdown_on,
)
from lightning_sdk.lightning_cloud import env

_CONFIG = {
    "featureFlags": [
        {"name": LOCKDOWN_FLAG, "value": "true"},
        {"name": UPLOADS_FLAG, "value": "false"},
        {"name": "someOtherFlag", "value": "on"},
    ]
}


@pytest.fixture(autouse=True)
def _fixture_lockdown_on(monkeypatch, tmp_path):
    """Use the real flags, read fresh in each test and cached under ``tmp_path``, instead of the conftest's."""
    monkeypatch.setattr(lockdown_status, "lockdown_flags", lockdown_flags)
    monkeypatch.setattr(lockdown_status, "_flags", lockdown_status._UNREAD)
    monkeypatch.setattr(lockdown_status, "_cache_path", lambda: tmp_path / "lockdown_flags.json")


def _new_process(monkeypatch) -> None:
    monkeypatch.setattr(lockdown_status, "_flags", lockdown_status._UNREAD)


def _config_response(body: object) -> MagicMock:
    response = MagicMock()
    response.json.return_value = body
    return response


def test_reads_the_flags_from_config() -> None:
    with patch("requests.get", return_value=_config_response(_CONFIG)) as get:
        flags = lockdown_flags()

    assert flags == {LOCKDOWN_FLAG: True, UPLOADS_FLAG: False, "someOtherFlag": False}
    assert get.call_args.args[0] == f"{env.LIGHTNING_CLOUD_URL}/v1/config"


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
    assert flags is not None
    assert flags[LOCKDOWN_FLAG] is True


@pytest.mark.parametrize(
    "entry",
    [
        {"url": "https://staging.lightning.ai", "flags": {LOCKDOWN_FLAG: False}, "checked_at": time.time()},
        {"url": env.LIGHTNING_CLOUD_URL, "flags": {LOCKDOWN_FLAG: False}, "checked_at": time.time() - 60 * 60},
        {"url": env.LIGHTNING_CLOUD_URL, "flags": {LOCKDOWN_FLAG: False}, "checked_at": time.time() + 60 * 60},
        {"url": env.LIGHTNING_CLOUD_URL, "flags": "nope", "checked_at": time.time()},
    ],
    ids=["other cloud url", "stale", "from the future", "malformed"],
)
def test_ignores_a_cache_entry_it_cannot_use(entry: dict) -> None:
    lockdown_status._cache_path().write_text(json.dumps(entry))

    with patch("requests.get", return_value=_config_response(_CONFIG)) as get:
        flags = lockdown_flags()

    assert get.call_count == 1
    assert flags is not None
    assert flags[LOCKDOWN_FLAG] is True


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
    ("flags", "on", "uploads_closed"),
    [
        ({LOCKDOWN_FLAG: True}, True, True),
        ({LOCKDOWN_FLAG: True, UPLOADS_FLAG: True}, True, False),
        ({LOCKDOWN_FLAG: False}, False, False),
        # a control plane that doesn't send apiLockdown is read as locked down, as the CLI was before the flags
        ({}, True, True),
        # unreadable: the server enforces the lockdown, so only the commands it never opens stay refused
        (None, True, False),
    ],
)
def test_lockdown_on_and_capability_closed(monkeypatch, flags, on: bool, uploads_closed: bool) -> None:
    monkeypatch.setattr(lockdown_status, "lockdown_flags", lambda: flags)

    assert lockdown_on() is on
    assert capability_closed(UPLOADS_FLAG) is uploads_closed
