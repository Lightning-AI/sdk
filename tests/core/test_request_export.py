import csv
import gzip
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests

from lightning_sdk.api import deployment_api as deployment_api_module
from lightning_sdk.api.deployment_api import (
    DEFAULT_REQUEST_CAPTURE_PATH,
    DeploymentApi,
    MissingRequestContentError,
)


class _FakeResponse:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class _FakeClient:
    def __init__(self, pages):
        self.pages = list(pages)
        self.list_calls = []
        self.content_calls = []

    def jobs_service_list_deployment_routing_telemetry(self, **kwargs):
        self.list_calls.append(kwargs)
        telemetry = self.pages.pop(0) if self.pages else []
        return SimpleNamespace(routing_telemetry=telemetry)

    def jobs_service_get_deployment_routing_telemetry_content(self, **kwargs):
        self.content_calls.append(kwargs)
        return SimpleNamespace(url=f"https://signed.example/{kwargs['request_id']}.json.gz")


def _telemetry(request_id, *, path=DEFAULT_REQUEST_CAPTURE_PATH, captured=True, status_code=200):
    return SimpleNamespace(
        id=request_id,
        received_at=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
        status_code=status_code,
        method="POST",
        path=path,
        duration=timedelta(milliseconds=125),
        resource_id="resource-id",
        captured=captured,
        request_body_size=123,
        response_body_size=456,
    )


def _gzipped_json(payload):
    return gzip.compress(json.dumps(payload).encode("utf-8"))


def _deployment():
    return SimpleNamespace(project_id="teamspace-id", id="deployment-id", name="deployment-name")


def _deployment_api(client):
    api = object.__new__(DeploymentApi)
    api._client = client
    return api


def test_export_defaults_to_chat_completions_and_writes_artifacts(tmp_path, monkeypatch):
    client = _FakeClient(
        pages=[
            [_telemetry("req-3"), _telemetry("req-2", captured=False)],
            [_telemetry("req-1")],
        ]
    )

    def fake_get(url, timeout):
        filename = url.rsplit("/", maxsplit=1)[-1]
        request_id = filename[: -len(".json.gz")]
        return _FakeResponse(
            _gzipped_json(
                {
                    "request_body": {"messages": [{"role": "user", "content": request_id}]},
                    "response_body": {"choices": [{"message": {"content": "ok"}}]},
                }
            )
        )

    monkeypatch.setattr("lightning_sdk.api.deployment_api.requests.get", fake_get)

    result = _deployment_api(client).export_request_captures(
        _deployment(),
        start=datetime(2026, 4, 20, tzinfo=timezone.utc),
        end=datetime(2026, 4, 22, tzinfo=timezone.utc),
        output_dir=tmp_path,
        status_codes=[200, 500],
        page_size=2,
    )

    assert result.row_count == 3
    assert result.captured_count == 2
    assert result.uncaptured_count == 1
    assert client.list_calls[0]["path"] == [DEFAULT_REQUEST_CAPTURE_PATH]
    assert client.list_calls[0]["status_code"] == [200, 500]
    assert "filter_successful" not in client.list_calls[0]
    assert "last_request_id" not in client.list_calls[0]
    assert client.list_calls[1]["last_request_id"] == "req-2"
    assert [call["request_id"] for call in client.content_calls] == ["req-3", "req-1"]

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["artifacts"] == {"csv": str(result.csv_path), "jsonl": str(result.jsonl_path)}
    assert manifest["teamspace_id"] == "teamspace-id"
    assert manifest["deployment_name"] == "deployment-name"
    assert manifest["paths"] == [DEFAULT_REQUEST_CAPTURE_PATH]

    jsonl_rows = [json.loads(line) for line in result.jsonl_path.read_text().splitlines()]
    assert jsonl_rows[0]["request_body"]["messages"][0]["content"] == "req-3"
    assert jsonl_rows[1]["request_body"] is None

    with result.csv_path.open(newline="", encoding="utf-8") as csv_file:
        csv_rows = list(csv.DictReader(csv_file))
    assert csv_rows[0]["request_body"] == '{"messages": [{"content": "req-3", "role": "user"}]}'
    assert csv_rows[1]["captured"] == "false"


def test_export_include_all_paths_omits_path_filter(tmp_path, monkeypatch):
    client = _FakeClient(pages=[[_telemetry("health-1", path="/health", captured=False)]])
    monkeypatch.setattr("lightning_sdk.api.deployment_api.requests.get", pytest.fail)

    result = _deployment_api(client).export_request_captures(
        _deployment(),
        start="2026-04-20T00:00:00Z",
        end="2026-04-22T00:00:00Z",
        output_dir=tmp_path,
        include_all_paths=True,
    )

    assert "path" not in client.list_calls[0]
    assert result.row_count == 1
    assert result.uncaptured_count == 1


def test_export_strict_mode_cleans_artifacts_when_manifest_write_fails(tmp_path, monkeypatch):
    client = _FakeClient(pages=[[_telemetry("uncaptured", captured=False)]])
    monkeypatch.setattr("lightning_sdk.api.deployment_api.requests.get", pytest.fail)

    def fail_manifest(**kwargs):
        raise RuntimeError("manifest failed")

    monkeypatch.setattr(deployment_api_module, "_build_manifest", fail_manifest)

    with pytest.raises(RuntimeError, match="manifest failed"):
        _deployment_api(client).export_request_captures(
            _deployment(),
            start="2026-04-20T00:00:00Z",
            end="2026-04-22T00:00:00Z",
            output_dir=tmp_path,
            strict=True,
        )

    assert not (tmp_path / "requests.csv").exists()
    assert not (tmp_path / "requests.jsonl").exists()
    assert not (tmp_path / "manifest.json").exists()


def test_export_counts_missing_content_and_strict_mode_raises(tmp_path, monkeypatch):
    client = _FakeClient(pages=[[_telemetry("missing")]])
    monkeypatch.setattr(
        "lightning_sdk.api.deployment_api.requests.get",
        lambda url, timeout: _FakeResponse(b"", status_code=404),
    )

    result = _deployment_api(client).export_request_captures(
        _deployment(),
        start="2026-04-20T00:00:00Z",
        end="2026-04-22T00:00:00Z",
        output_dir=tmp_path,
    )

    assert result.missing_content_count == 1
    jsonl_row = json.loads(result.jsonl_path.read_text())
    assert jsonl_row["content_missing"] is True

    strict_dir = tmp_path / "strict"
    with pytest.raises(MissingRequestContentError):
        _deployment_api(_FakeClient(pages=[[_telemetry("missing")]])).export_request_captures(
            _deployment(),
            start="2026-04-20T00:00:00Z",
            end="2026-04-22T00:00:00Z",
            output_dir=strict_dir,
            strict=True,
        )
    assert not any(strict_dir.iterdir())


def test_export_preserves_raw_content_when_json_parse_fails(tmp_path, monkeypatch):
    client = _FakeClient(pages=[[_telemetry("malformed")]])
    monkeypatch.setattr(
        "lightning_sdk.api.deployment_api.requests.get",
        lambda url, timeout: _FakeResponse(gzip.compress(b"not-json")),
    )

    result = _deployment_api(client).export_request_captures(
        _deployment(),
        start="2026-04-20T00:00:00Z",
        end="2026-04-22T00:00:00Z",
        output_dir=tmp_path,
    )

    assert result.content_error_count == 1
    jsonl_row = json.loads(result.jsonl_path.read_text())
    assert jsonl_row["raw_content"] == "not-json"
    assert "failed to parse captured content" in jsonl_row["content_error"]


def test_export_records_download_decode_errors(tmp_path, monkeypatch):
    client = _FakeClient(pages=[[_telemetry("bad-gzip")]])
    monkeypatch.setattr(
        "lightning_sdk.api.deployment_api.requests.get",
        lambda url, timeout: _FakeResponse(b"\x1f\x8bbad"),
    )

    result = _deployment_api(client).export_request_captures(
        _deployment(),
        start="2026-04-20T00:00:00Z",
        end="2026-04-22T00:00:00Z",
        output_dir=tmp_path,
    )

    assert result.content_error_count == 1
    jsonl_row = json.loads(result.jsonl_path.read_text())
    assert jsonl_row["request_body"] is None
    assert "failed to download captured content" in jsonl_row["content_error"]


def test_export_records_missing_request_id_without_content_endpoint_call(tmp_path):
    client = _FakeClient(pages=[[_telemetry(None)]])

    result = _deployment_api(client).export_request_captures(
        _deployment(),
        start="2026-04-20T00:00:00Z",
        end="2026-04-22T00:00:00Z",
        output_dir=tmp_path,
    )

    assert client.content_calls == []
    assert result.missing_content_count == 1
    jsonl_row = json.loads(result.jsonl_path.read_text())
    assert jsonl_row["content_missing"] is True
    assert "missing request id" in jsonl_row["content_error"]


def test_export_rejects_unbounded_window(tmp_path):
    with pytest.raises(ValueError, match="start and end are required"):
        _deployment_api(_FakeClient(pages=[])).export_request_captures(
            _deployment(),
            start=None,
            end="2026-04-22T00:00:00Z",
            output_dir=tmp_path,
        )


def test_export_rejects_ambiguous_path_arguments(tmp_path):
    with pytest.raises(ValueError, match="paths must not be empty"):
        _deployment_api(_FakeClient(pages=[])).export_request_captures(
            _deployment(),
            start="2026-04-20T00:00:00Z",
            end="2026-04-22T00:00:00Z",
            output_dir=tmp_path,
            paths=[],
        )


def test_export_rejects_existing_artifacts_unless_overwrite_is_enabled(tmp_path):
    (tmp_path / "requests.csv").write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="requests.csv"):
        _deployment_api(_FakeClient(pages=[])).export_request_captures(
            _deployment(),
            start="2026-04-20T00:00:00Z",
            end="2026-04-22T00:00:00Z",
            output_dir=tmp_path,
        )

    result = _deployment_api(_FakeClient(pages=[])).export_request_captures(
        _deployment(),
        start="2026-04-20T00:00:00Z",
        end="2026-04-22T00:00:00Z",
        output_dir=tmp_path,
        overwrite=True,
    )

    assert result.row_count == 0

    with pytest.raises(ValueError, match="mutually exclusive"):
        _deployment_api(_FakeClient(pages=[])).export_request_captures(
            _deployment(),
            start="2026-04-20T00:00:00Z",
            end="2026-04-22T00:00:00Z",
            output_dir=tmp_path,
            include_all_paths=True,
            paths=[],
        )
