import json

import click
import pytest

from lightning_sdk.cli.deployment._byom_ack import (
    create_with_acknowledgement,
    extract_unacked_warnings,
    resolve_acknowledgements,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException


def _api_exc(message):
    e = ApiException(status=400, reason="Bad Request")
    e.body = json.dumps({"code": 3, "message": message})
    return e


def test_extract_unacked_warnings_multiple():
    e = _api_exc("unacknowledged BYOM warnings: BYOM_INSUFFICIENT_VRAM_ESTIMATE, BYOM_USING_STALE_HF_METADATA")
    assert extract_unacked_warnings(e) == ["BYOM_INSUFFICIENT_VRAM_ESTIMATE", "BYOM_USING_STALE_HF_METADATA"]


def test_extract_unacked_warnings_single():
    e = _api_exc("unacknowledged BYOM warnings: BYOM_INSUFFICIENT_VRAM_ESTIMATE")
    assert extract_unacked_warnings(e) == ["BYOM_INSUFFICIENT_VRAM_ESTIMATE"]


def test_extract_unacked_warnings_ignores_hard_errors():
    # Hard errors use a different format ("CODE: message; ...") and never carry the prefix.
    e = _api_exc("BYOM_MODEL_NOT_FOUND: model does not exist")
    assert extract_unacked_warnings(e) == []


def test_extract_unacked_warnings_from_reason_only():
    e = ApiException(status=400, reason="unacknowledged BYOM warnings: BYOM_INSUFFICIENT_VRAM_ESTIMATE")
    assert extract_unacked_warnings(e) == ["BYOM_INSUFFICIENT_VRAM_ESTIMATE"]


def test_extract_unacked_warnings_none_on_unrelated_error():
    e = _api_exc("some other error")
    assert extract_unacked_warnings(e) == []


def test_resolve_force_acks_all():
    assert resolve_acknowledgements(["A", "B"], force=True, interactive=False) == ["A", "B"]


def test_resolve_non_interactive_no_force_returns_empty():
    assert resolve_acknowledgements(["A"], force=False, interactive=False) == []


def test_resolve_interactive_accept(monkeypatch):
    monkeypatch.setattr("lightning_sdk.cli.deployment._byom_ack.click.confirm", lambda *_a, **_k: True)
    assert resolve_acknowledgements(["A", "B"], force=False, interactive=True) == ["A", "B"]


def test_resolve_interactive_decline(monkeypatch):
    monkeypatch.setattr("lightning_sdk.cli.deployment._byom_ack.click.confirm", lambda *_a, **_k: False)
    assert resolve_acknowledgements(["A"], force=False, interactive=True) == []


def test_create_with_ack_success_first_try():
    assert create_with_acknowledgement(lambda _acks: "ok", acks=[], force=False, interactive=False) == "ok"


def test_create_with_ack_force_retries_then_succeeds():
    calls = []

    def create_fn(acknowledged):
        calls.append(list(acknowledged))
        if len(calls) == 1:
            raise _api_exc("unacknowledged BYOM warnings: BYOM_X")
        return "ok"

    assert create_with_acknowledgement(create_fn, acks=[], force=True, interactive=False) == "ok"
    assert calls == [[], ["BYOM_X"]]


def test_create_with_ack_reraises_non_warning_errors():
    def create_fn(_acknowledged):
        raise _api_exc("BYOM_MODEL_NOT_FOUND: nope")

    with pytest.raises(ApiException):
        create_with_acknowledgement(create_fn, acks=[], force=True, interactive=False)


def test_create_with_ack_guard_raises_when_no_new_codes():
    def create_fn(_acknowledged):
        raise _api_exc("unacknowledged BYOM warnings: BYOM_X")

    with pytest.raises(click.UsageError):
        create_with_acknowledgement(create_fn, acks=["BYOM_X"], force=True, interactive=False)
