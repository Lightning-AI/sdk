import csv
import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

import lightning_sdk.api.lightning_storage_upload as lightning_storage_upload_module
from lightning_sdk.api import deployment_api as deployment_api_module
from lightning_sdk.api.deployment_api import (
    DEFAULT_REQUEST_CAPTURE_PATH,
    DeploymentApi,
    MissingRequestContentError,
)
from lightning_sdk.lightning_cloud.openapi import DataConnectionServiceCreateDataConnectionBody, V1R2DataConnection


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
        self.project_cluster_bindings = [SimpleNamespace(cluster_id="project-cluster-id")]
        self.preferred_cluster = "preferred-cluster-id"
        self.project_name = "my-teamspace"
        self.project_owner_name = "my-org"
        self.project_owner_id = "owner-id"
        self.project_owner_type = "organization"

    def jobs_service_list_deployment_routing_telemetry(self, **kwargs):
        self.list_calls.append(kwargs)
        telemetry = self.pages.pop(0) if self.pages else []
        return SimpleNamespace(routing_telemetry=telemetry)

    def jobs_service_get_deployment_routing_telemetry_content(self, **kwargs):
        self.content_calls.append(kwargs)
        return SimpleNamespace(url=f"https://signed.example/{kwargs['request_id']}.json.gz")

    def projects_service_list_project_cluster_bindings(self, project_id):
        return SimpleNamespace(clusters=self.project_cluster_bindings)

    def projects_service_get_project(self, project_id):
        return SimpleNamespace(
            name=self.project_name,
            owner_id=self.project_owner_id,
            owner_type=self.project_owner_type,
            project_settings=SimpleNamespace(preferred_cluster=self.preferred_cluster),
        )

    def organizations_service_get_organization(self, id):
        return SimpleNamespace(name=self.project_owner_name)

    def user_service_search_users(self, query):
        users = []
        if query == self.project_owner_id:
            users.append(SimpleNamespace(id=self.project_owner_id, username=self.project_owner_name))
        return SimpleNamespace(users=users)


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


def test_export_optionally_uploads_artifacts_to_lightning_storage(tmp_path, monkeypatch):
    monkeypatch.delenv("LIGHTNING_CLUSTER_ID", raising=False)
    client = _FakeClient(pages=[[_telemetry("health-1", path="/health", captured=False)]])
    pending_connection = SimpleNamespace(
        id="data-connection-id",
        name="blackbox-exports",
        r2=SimpleNamespace(source="tmp", account_id="tmp"),
        writable=True,
        state="DATA_CONNECTION_STATE_PENDING",
    )
    ready_connection = SimpleNamespace(
        id="data-connection-id",
        name="blackbox-exports",
        r2=SimpleNamespace(source="r2://bucket-name", account_id="account-id"),
        writable=True,
        state="DATA_CONNECTION_STATE_CREATED",
    )
    client.data_connection_service_list_data_connections = MagicMock(
        side_effect=[
            SimpleNamespace(data_connections=[]),
            SimpleNamespace(data_connections=[pending_connection]),
            SimpleNamespace(data_connections=[ready_connection]),
        ]
    )
    client.data_connection_service_create_data_connection = MagicMock(
        return_value=SimpleNamespace(
            id="data-connection-id",
            name="blackbox-exports",
            r2=SimpleNamespace(source="tmp", account_id="tmp"),
            writable=True,
            cluster_id="data-connection-cluster-id",
        )
    )
    monkeypatch.setattr("lightning_sdk.api.deployment_api.requests.get", pytest.fail)
    sleeps = []
    monkeypatch.setattr(lightning_storage_upload_module, "sleep", lambda seconds: sleeps.append(seconds))

    uploads = []
    manifest_uploads = []

    class _FakeUploader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            uploads.append(kwargs)

        def __call__(self):
            if self.kwargs["remote_path"].endswith("manifest.json"):
                manifest_uploads.append(json.loads(Path(self.kwargs["file_path"]).read_text()))
            return

    monkeypatch.setattr(deployment_api_module, "_FileUploader", _FakeUploader)

    result = _deployment_api(client).export_request_captures(
        _deployment(),
        start="2026-04-20T00:00:00Z",
        end="2026-04-22T00:00:00Z",
        output_dir=tmp_path,
        include_all_paths=True,
        remote_path="lightning_storage/blackbox-exports/daily/2026-04-22",
    )

    assert result.uploaded_artifacts == {
        "csv": "/teamspace/lightning_storage/blackbox-exports/daily/2026-04-22/requests.csv",
        "jsonl": "/teamspace/lightning_storage/blackbox-exports/daily/2026-04-22/requests.jsonl",
        "manifest": "/teamspace/lightning_storage/blackbox-exports/daily/2026-04-22/manifest.json",
    }
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["uploaded_artifacts"] == result.uploaded_artifacts
    assert client.data_connection_service_list_data_connections.call_count == 3
    create_kwargs = client.data_connection_service_create_data_connection.call_args.kwargs
    assert create_kwargs["project_id"] == "teamspace-id"
    assert create_kwargs["body"] == DataConnectionServiceCreateDataConnectionBody(
        name="blackbox-exports",
        create_resources=True,
        force=True,
        writable=True,
        r2=V1R2DataConnection(name="blackbox-exports"),
    )
    assert [upload["remote_path"] for upload in uploads] == [
        "daily/2026-04-22/requests.csv",
        "daily/2026-04-22/requests.jsonl",
        "daily/2026-04-22/manifest.json",
    ]
    assert manifest_uploads[0]["uploaded_artifacts"] == result.uploaded_artifacts
    assert all(upload["data_connection_id"] == "data-connection-id" for upload in uploads)
    assert all(upload["cloud_account"] == "project-cluster-id" for upload in uploads)
    assert sleeps == [lightning_storage_upload_module.LIGHTNING_STORAGE_POLL_INTERVAL_SECONDS]


def test_export_keeps_local_manifest_honest_when_manifest_upload_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("LIGHTNING_CLUSTER_ID", raising=False)
    client = _FakeClient(pages=[[_telemetry("health-1", path="/health", captured=False)]])
    client.data_connection_service_list_data_connections = MagicMock(
        return_value=SimpleNamespace(
            data_connections=[
                SimpleNamespace(
                    id="data-connection-id",
                    name="blackbox-exports",
                    r2=SimpleNamespace(source="r2://bucket-name", account_id="account-id"),
                    writable=True,
                    state="DATA_CONNECTION_STATE_CREATED",
                )
            ]
        )
    )
    monkeypatch.setattr("lightning_sdk.api.deployment_api.requests.get", pytest.fail)

    uploads = []

    class _FakeUploader:
        def __init__(self, **kwargs):
            self.remote_path = kwargs["remote_path"]
            uploads.append(kwargs)

        def __call__(self):
            if self.remote_path.endswith("manifest.json"):
                raise RuntimeError("manifest upload failed")
            return

    monkeypatch.setattr(deployment_api_module, "_FileUploader", _FakeUploader)

    with pytest.raises(RuntimeError, match=r"failed to upload request export artifact .*manifest\.json"):
        _deployment_api(client).export_request_captures(
            _deployment(),
            start="2026-04-20T00:00:00Z",
            end="2026-04-22T00:00:00Z",
            output_dir=tmp_path,
            include_all_paths=True,
            remote_path="lightning_storage/blackbox-exports/daily/2026-04-22",
        )

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["uploaded_artifacts"] == {
        "csv": "/teamspace/lightning_storage/blackbox-exports/daily/2026-04-22/requests.csv",
        "jsonl": "/teamspace/lightning_storage/blackbox-exports/daily/2026-04-22/requests.jsonl",
    }


def test_export_does_not_resolve_upload_target_before_local_manifest_is_written(tmp_path, monkeypatch):
    client = _FakeClient(pages=[[_telemetry("health-1", path="/health", captured=False)]])
    monkeypatch.setattr("lightning_sdk.api.deployment_api.requests.get", pytest.fail)

    def fail_manifest(**kwargs):
        raise RuntimeError("manifest failed")

    monkeypatch.setattr(deployment_api_module, "_build_manifest", fail_manifest)
    monkeypatch.setattr(
        deployment_api_module,
        "_resolve_lightning_storage_upload_target",
        lambda **kwargs: pytest.fail("upload target should not resolve before local manifest exists"),
    )

    with pytest.raises(RuntimeError, match="manifest failed"):
        _deployment_api(client).export_request_captures(
            _deployment(),
            start="2026-04-20T00:00:00Z",
            end="2026-04-22T00:00:00Z",
            output_dir=tmp_path,
            include_all_paths=True,
            remote_path="lightning_storage/blackbox-exports/daily/2026-04-22",
        )


def test_export_records_partial_remote_uploads_when_jsonl_upload_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("LIGHTNING_CLUSTER_ID", raising=False)
    client = _FakeClient(pages=[[_telemetry("health-1", path="/health", captured=False)]])
    client.data_connection_service_list_data_connections = MagicMock(
        return_value=SimpleNamespace(
            data_connections=[
                SimpleNamespace(
                    id="data-connection-id",
                    name="blackbox-exports",
                    r2=SimpleNamespace(source="r2://bucket-name", account_id="account-id"),
                    writable=True,
                    state="DATA_CONNECTION_STATE_CREATED",
                )
            ]
        )
    )
    monkeypatch.setattr("lightning_sdk.api.deployment_api.requests.get", pytest.fail)

    class _FakeUploader:
        def __init__(self, **kwargs):
            self.remote_path = kwargs["remote_path"]

        def __call__(self):
            if self.remote_path.endswith("requests.jsonl"):
                raise RuntimeError("jsonl upload failed")
            return

    monkeypatch.setattr(deployment_api_module, "_FileUploader", _FakeUploader)

    with pytest.raises(RuntimeError, match=r"failed to upload request export artifact .*requests\.jsonl"):
        _deployment_api(client).export_request_captures(
            _deployment(),
            start="2026-04-20T00:00:00Z",
            end="2026-04-22T00:00:00Z",
            output_dir=tmp_path,
            include_all_paths=True,
            remote_path="lightning_storage/blackbox-exports/daily/2026-04-22",
        )

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["uploaded_artifacts"] == {
        "csv": "/teamspace/lightning_storage/blackbox-exports/daily/2026-04-22/requests.csv",
    }


def test_lightning_storage_upload_cloud_account_errors_when_no_clusters_are_bound(monkeypatch):
    monkeypatch.delenv("LIGHTNING_CLUSTER_ID", raising=False)
    client = _FakeClient(pages=[])
    client.project_cluster_bindings = []
    client.preferred_cluster = None

    with pytest.raises(RuntimeError, match="no clusters are bound to the teamspace"):
        deployment_api_module._resolve_lightning_storage_upload_cloud_account(
            client=client,
            teamspace_id="teamspace-id",
        )


def test_wait_for_lightning_storage_folder_ready_respects_timeout_window(monkeypatch):
    client = _FakeClient(pages=[])
    pending_connection = SimpleNamespace(
        id="data-connection-id",
        name="blackbox-exports",
        r2=SimpleNamespace(source="tmp", account_id="tmp"),
        writable=True,
        state="DATA_CONNECTION_STATE_PENDING",
    )
    ready_connection = SimpleNamespace(
        id="data-connection-id",
        name="blackbox-exports",
        r2=SimpleNamespace(source="r2://bucket-name", account_id="account-id"),
        writable=True,
        state="DATA_CONNECTION_STATE_CREATED",
    )
    client.data_connection_service_list_data_connections = MagicMock(
        side_effect=[
            SimpleNamespace(data_connections=[pending_connection]),
            SimpleNamespace(data_connections=[pending_connection]),
            SimpleNamespace(data_connections=[pending_connection]),
            SimpleNamespace(data_connections=[ready_connection]),
        ]
    )
    clock = {"now": 0.0}
    sleeps = []

    monkeypatch.setattr(lightning_storage_upload_module, "monotonic", lambda: clock["now"])

    def fake_sleep(seconds):
        sleeps.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr(lightning_storage_upload_module, "sleep", fake_sleep)

    result = deployment_api_module._wait_for_lightning_storage_folder_ready(
        client=client,
        teamspace_id="teamspace-id",
        folder_name="blackbox-exports",
        timeout_seconds=31,
        poll_interval_seconds=10,
    )

    assert result == ready_connection
    assert sleeps == [10, 10, 10]


def test_wait_for_lightning_storage_folder_ready_caps_final_sleep(monkeypatch):
    client = _FakeClient(pages=[])
    pending_connection = SimpleNamespace(
        id="data-connection-id",
        name="blackbox-exports",
        r2=SimpleNamespace(source="tmp", account_id="tmp"),
        writable=True,
        state="DATA_CONNECTION_STATE_PENDING",
    )
    client.data_connection_service_list_data_connections = MagicMock(
        side_effect=[
            SimpleNamespace(data_connections=[pending_connection]),
            SimpleNamespace(data_connections=[pending_connection]),
            SimpleNamespace(data_connections=[pending_connection]),
            SimpleNamespace(data_connections=[pending_connection]),
            SimpleNamespace(data_connections=[pending_connection]),
        ]
    )
    clock = {"now": 0.0}
    sleeps = []

    monkeypatch.setattr(lightning_storage_upload_module, "monotonic", lambda: clock["now"])

    def fake_sleep(seconds):
        sleeps.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr(lightning_storage_upload_module, "sleep", fake_sleep)

    with pytest.raises(RuntimeError, match="was not ready for upload within 31s"):
        deployment_api_module._wait_for_lightning_storage_folder_ready(
            client=client,
            teamspace_id="teamspace-id",
            folder_name="blackbox-exports",
            timeout_seconds=31,
            poll_interval_seconds=10,
        )

    assert sleeps == [10, 10, 10, 1]


def test_wait_for_lightning_storage_folder_ready_sleeps_before_repolling_initial_connection(monkeypatch):
    client = _FakeClient(pages=[])
    pending_connection = SimpleNamespace(
        id="data-connection-id",
        name="blackbox-exports",
        r2=SimpleNamespace(source="tmp", account_id="tmp"),
        writable=True,
        state="DATA_CONNECTION_STATE_PENDING",
    )
    ready_connection = SimpleNamespace(
        id="data-connection-id",
        name="blackbox-exports",
        r2=SimpleNamespace(source="r2://bucket-name", account_id="account-id"),
        writable=True,
        state="DATA_CONNECTION_STATE_CREATED",
    )
    client.data_connection_service_list_data_connections = MagicMock(
        return_value=SimpleNamespace(data_connections=[ready_connection])
    )
    clock = {"now": 0.0}
    sleeps = []

    monkeypatch.setattr(lightning_storage_upload_module, "monotonic", lambda: clock["now"])

    def fake_sleep(seconds):
        sleeps.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr(lightning_storage_upload_module, "sleep", fake_sleep)

    result = deployment_api_module._wait_for_lightning_storage_folder_ready(
        client=client,
        teamspace_id="teamspace-id",
        folder_name="blackbox-exports",
        initial_connection=pending_connection,
        timeout_seconds=31,
        poll_interval_seconds=10,
    )

    assert result == ready_connection
    assert sleeps == [10]
    client.data_connection_service_list_data_connections.assert_called_once()


def test_export_prefers_project_default_cluster_for_lightning_storage_upload(tmp_path, monkeypatch):
    monkeypatch.delenv("LIGHTNING_CLUSTER_ID", raising=False)
    client = _FakeClient(pages=[[_telemetry("health-1", path="/health", captured=False)]])
    client.project_cluster_bindings = [
        SimpleNamespace(cluster_id="project-cluster-a"),
        SimpleNamespace(cluster_id="project-cluster-b"),
    ]
    client.preferred_cluster = "project-cluster-b"
    client.data_connection_service_list_data_connections = MagicMock(
        return_value=SimpleNamespace(
            data_connections=[
                SimpleNamespace(
                    id="data-connection-id",
                    name="blackbox-exports",
                    r2=SimpleNamespace(source="r2://bucket-name", account_id="account-id"),
                    writable=True,
                    state="DATA_CONNECTION_STATE_CREATED",
                    cluster_id="data-connection-cluster-id",
                )
            ]
        )
    )
    monkeypatch.setattr("lightning_sdk.api.deployment_api.requests.get", pytest.fail)

    uploads = []

    class _FakeUploader:
        def __init__(self, **kwargs):
            uploads.append(kwargs)

        def __call__(self):
            return None

    monkeypatch.setattr(deployment_api_module, "_FileUploader", _FakeUploader)

    _deployment_api(client).export_request_captures(
        _deployment(),
        start="2026-04-20T00:00:00Z",
        end="2026-04-22T00:00:00Z",
        output_dir=tmp_path,
        include_all_paths=True,
        remote_path="lightning_storage/blackbox-exports/daily/2026-04-22",
    )

    assert all(upload["cloud_account"] == "project-cluster-b" for upload in uploads)


@pytest.mark.parametrize(
    ("remote_path", "expected"),
    [
        (
            "lightning_storage/blackbox-exports/daily/2026-04-22",
            ("blackbox-exports", ("daily", "2026-04-22")),
        ),
        (
            "teamspace/lightning_storage/blackbox-exports/daily/2026-04-22",
            ("blackbox-exports", ("daily", "2026-04-22")),
        ),
        (
            "/teamspace/lightning_storage/blackbox-exports/daily/2026-04-22",
            ("blackbox-exports", ("daily", "2026-04-22")),
        ),
        (
            "lit://my-org/my-teamspace/lightning_storage/blackbox-exports/daily/2026-04-22",
            ("blackbox-exports", ("daily", "2026-04-22")),
        ),
        (
            "lightning_storage//blackbox-exports//daily/2026-04-22",
            ("blackbox-exports", ("daily", "2026-04-22")),
        ),
    ],
)
def test_parse_remote_upload_path_accepts_lightning_storage_forms(remote_path, expected):
    assert deployment_api_module._parse_lightning_storage_path(remote_path) == expected


@pytest.mark.parametrize(
    ("remote_path", "match"),
    [
        ("blackbox-exports/daily", "lightning_storage destinations only"),
        ("uploads/blackbox-exports/daily", "lightning_storage destinations only"),
        ("lit://my-org/my-teamspace/uploads/blackbox-exports/daily", "lightning_storage destinations only"),
        ("lightning_storage/blackbox-exports/../daily", r"must not be '\.\.'"),
    ],
)
def test_export_rejects_invalid_remote_path(tmp_path, remote_path, match):
    with pytest.raises(ValueError, match=match):
        _deployment_api(_FakeClient(pages=[])).export_request_captures(
            _deployment(),
            start="2026-04-20T00:00:00Z",
            end="2026-04-22T00:00:00Z",
            output_dir=tmp_path,
            remote_path=remote_path,
        )


@pytest.mark.parametrize(
    ("remote_path", "match"),
    [
        (
            "lit://my-org/other-teamspace/lightning_storage/blackbox-exports/daily/2026-04-22",
            "expected teamspace 'my-teamspace'",
        ),
        (
            "lit://other-org/my-teamspace/lightning_storage/blackbox-exports/daily/2026-04-22",
            "expected owner 'my-org'",
        ),
    ],
)
def test_export_rejects_lit_remote_path_for_other_teamspace(tmp_path, remote_path, match):
    with pytest.raises(ValueError, match=match):
        _deployment_api(_FakeClient(pages=[])).export_request_captures(
            _deployment(),
            start="2026-04-20T00:00:00Z",
            end="2026-04-22T00:00:00Z",
            output_dir=tmp_path,
            remote_path=remote_path,
        )


@pytest.mark.parametrize(
    ("remote_path", "match"),
    [
        (
            "lit://my-org//lightning_storage/blackbox-exports/daily/2026-04-22",
            "non-empty teamspace",
        ),
        (
            "lit:///my-teamspace/lightning_storage/blackbox-exports/daily/2026-04-22",
            "non-empty owner",
        ),
    ],
)
def test_export_rejects_lit_remote_path_with_empty_owner_or_teamspace(tmp_path, remote_path, match):
    with pytest.raises(ValueError, match=match):
        _deployment_api(_FakeClient(pages=[])).export_request_captures(
            _deployment(),
            start="2026-04-20T00:00:00Z",
            end="2026-04-22T00:00:00Z",
            output_dir=tmp_path,
            remote_path=remote_path,
        )


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

    with pytest.raises(FileExistsError, match=r"requests\.csv"):
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
