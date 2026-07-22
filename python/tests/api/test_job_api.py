import json
import sys
import types
from typing import List
from unittest import mock

import pytest

from lightning_sdk.api.job_api import (
    JobApiV2,
    _decode_log_messages,
    _format_log_timestamp,
    _job_logs_ws_url,
)
from lightning_sdk.lightning_cloud.openapi import (
    JobsServiceUpdateJobBody,
    V1Job,
    V1JobSpec,
    V1PathMapping,
)
from lightning_sdk.machine import Machine
from lightning_sdk.status import Status


def test_job_v2_submit_job(mocker_auth):
    from lightning_sdk.lightning_cloud.openapi import JobsServiceCreateJobBody, V1EnvVar, V1JobSpec

    job_api = JobApiV2()

    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock

    job_api.submit_job(
        name="test-job",
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        image="",
        studio_id="st-abc",
        machine=Machine.T4_X_4,
        interruptible=False,
        env={"key": "value"},
        command="echo hello",
        image_credentials=None,
        cloud_account_auth=True,
        entrypoint="sh -c",
        path_mappings=None,
    )

    spec = V1JobSpec(
        cloudspace_id="st-abc",
        cluster_id="c-abc",
        command="echo hello",
        env=[V1EnvVar(name="key", value="value")],
        image="",
        instance_name="lit-t4-4",
        run_id=mock.ANY,
        spot=False,
        image_cluster_credentials=True,
        image_secret_ref="",
        entrypoint="sh -c",
        path_mappings=[],
        volumes=[],
    )
    body = JobsServiceCreateJobBody(name="test-job", spec=spec)
    create_job_mock.assert_called_once_with(project_id="ts-abc", body=body)

    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock
    job_api.submit_job(
        name="test-job",
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        studio_id="",
        image="image-abc",
        machine="some-dummy-instance-type",
        interruptible=True,
        env=None,
        command=None,
        image_credentials="dockerhub",
        cloud_account_auth=False,
        entrypoint="sh -c",
        path_mappings={"/output2": "data2:some-other-path", "/output": "data:some-path"},
    )

    spec = V1JobSpec(
        cloudspace_id="",
        cluster_id="c-abc",
        command="",
        env=[],
        image="image-abc",
        instance_name="some-dummy-instance-type",
        run_id=mock.ANY,
        spot=True,
        image_cluster_credentials=False,
        image_secret_ref="dockerhub",
        entrypoint="sh -c",
        path_mappings=[
            V1PathMapping(container_path="/output2", connection_name="data2", connection_path="some-other-path"),
            V1PathMapping(container_path="/output", connection_name="data", connection_path="some-path"),
        ],
        volumes=[],
    )
    body = JobsServiceCreateJobBody(name="test-job", spec=spec)
    create_job_mock.assert_called_once_with(project_id="ts-abc", body=body)
    create_job_mock.assert_called_once_with(project_id="ts-abc", body=body)


def test_job_v2_submit_job_threads_placement_group_id(mocker_auth):
    job_api = JobApiV2()
    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock

    job_api.submit_job(
        name="test-job",
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        image="image-abc",
        studio_id="",
        machine=Machine.CPU,
        interruptible=False,
        env=None,
        command="echo hello",
        image_credentials=None,
        cloud_account_auth=False,
        entrypoint="sh -c",
        path_mappings=None,
        placement_group_id="pg-1",
    )

    body = create_job_mock.call_args.kwargs["body"]
    assert body.spec.placement_group_id == "pg-1"


def test_get_job_by_name(mocker_auth):
    job_api = JobApiV2()

    get_job_by_name_mock = mock.MagicMock()
    job_api._client.jobs_service_find_job = get_job_by_name_mock

    job_api.get_job_by_name("test-job", "ts-abc")
    get_job_by_name_mock.assert_called_once_with(name="test-job", project_id="ts-abc")


def test_get_job_v2(mocker_auth):
    job_api = JobApiV2()

    get_job_mock = mock.MagicMock()
    job_api._client.jobs_service_get_job = get_job_mock

    job_api.get_job("test-job-id", "ts-abc")
    get_job_mock.assert_called_once_with(id="test-job-id", project_id="ts-abc")


@pytest.mark.parametrize(
    ("internal_state", "expected_state"),
    [
        ("pending", Status.Pending),
        ("running", Status.Running),
        ("stopped", Status.Stopped),
        ("completed", Status.Completed),
        ("failed", Status.Failed),
        ("unknown", Status.Pending),
    ],
)
def test_translate_state(mocker_auth, internal_state, expected_state):
    job_api = JobApiV2()
    assert job_api._job_state_to_external(internal_state) == expected_state


@pytest.mark.parametrize(
    ("instance_name", "instance_type", "expected_machine"),
    [
        ("g4dn.12xlarge", None, Machine.T4_X_4),
        ("p4d.24xlarge", "p4d.24xlarge", Machine.A100_X_8),
        ("unknown", "p4d.24xlarge", Machine.A100_X_8),
        ("unknown", "", Machine("unknown", "unknown")),
        ("", "unknown", Machine("unknown", "unknown")),
    ],
)
def test_machine_translate(
    mocker_auth, internal_studio_api_mocker_get_machine, instance_name, instance_type, expected_machine
):
    job_api = JobApiV2()

    spec = V1JobSpec(
        instance_name=instance_name,
        instance_type=instance_type,
        cluster_id="cluster_abc",
    )

    assert job_api._get_job_machine_from_spec(spec, teamspace_id="my-teamspace", org_id="test-org") == expected_machine


@pytest.mark.parametrize(
    ("job_states", "total_calls_get_job", "called_update_job"),
    [
        (["running", "stopped"], 2, True),
        (["running", "completed"], 2, True),
        (["stopped"], 1, False),
        (["completed"], 1, False),
        (["failed"], 1, False),
        (["pending", "stopped"], 2, True),
        (["pending", "running", "stopped"], 3, True),
        (["stopping", "stopping", "stopping", "stopped"], 4, False),
    ],
)
def test_jobv2_stop(mocker_auth, job_states: List[str], total_calls_get_job: int, called_update_job: bool):
    job_api = JobApiV2()

    def get_job_side_effect(*args, **kwargs):
        while job_states:
            return V1Job(id="test-job-id", state=job_states.pop(0), spec=V1JobSpec(cloudspace_id="cloudspace-id"))

        return V1Job(id="test-job-id", state="stopped", spec=V1JobSpec(cloudspace_id="cloudspace-id"))

    get_job_mock = mock.MagicMock()
    get_job_mock.side_effect = get_job_side_effect
    job_api._client.jobs_service_get_job = get_job_mock

    update_job_mock = mock.MagicMock()
    job_api._client.jobs_service_update_job = update_job_mock

    job_api.stop_job("test-job-id", "ts-abc")

    assert get_job_mock.call_count == total_calls_get_job

    if called_update_job:
        update_job_mock.assert_called_once_with(
            id="test-job-id", project_id="ts-abc", body=JobsServiceUpdateJobBody(state="stop")
        )
    else:
        update_job_mock.assert_not_called()


@pytest.mark.parametrize(
    ("cloudspace_id", "expected_cloudspace_id"), [(None, ""), ("cloudspace-id", "cloudspace-id"), ("", "")]
)
def test_jobv2_delete(mocker_auth, cloudspace_id, expected_cloudspace_id):
    job_api = JobApiV2()

    delete_job_mock = mock.MagicMock()
    job_api._client.jobs_service_delete_job = delete_job_mock

    job_api.delete_job("test-job-id", "ts-abc", cloudspace_id)

    delete_job_mock.assert_called_once_with(id="test-job-id", project_id="ts-abc", cloudspace_id=expected_cloudspace_id)


# ---------------------------------------------------------------------------
# live log streaming
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"seconds": 0, "nanos": 0}, "1970-01-01T00:00:00+00:00"),
        ({"seconds": 1_700_000_000}, "2023-11-14T22:13:20+00:00"),
        ({"nanos": 5}, None),  # no seconds -> cannot build a timestamp
        ("2023-11-14T22:13:20Z", "2023-11-14T22:13:20Z"),  # already-formatted string passes through
        (None, None),
        (123, None),  # unexpected type
    ],
)
def test_format_log_timestamp(value, expected):
    assert _format_log_timestamp(value) == expected


def test_decode_log_messages_plain_and_json():
    # a JSON array of entries -> one line per entry, using the `message` field
    frame = json.dumps([{"message": "hello"}, {"Message": "world"}])
    assert list(_decode_log_messages(frame)) == ["hello", "world"]

    # non-JSON payloads are yielded verbatim
    assert list(_decode_log_messages("not json")) == ["not json"]


def test_decode_log_messages_with_timestamps():
    frame = json.dumps(
        [
            {"message": "hello", "timestamp": {"seconds": 0, "nanos": 0}},
            {"message": "no-ts"},  # missing timestamp -> line unchanged
        ]
    )
    assert list(_decode_log_messages(frame, timestamps=True)) == [
        "1970-01-01T00:00:00+00:00 hello",
        "no-ts",
    ]


def test_job_logs_ws_url_builds_websocket_url():
    url = _job_logs_ws_url("ts-abc", "job-1", follow=True, tail=50, rank=2)

    assert url.startswith("wss://")
    assert "/v1/projects/ts-abc/jobs/job-1/logs" in url
    assert "follow=true" in url
    assert "direction=forward" in url
    assert "tail=50" in url
    assert "rank=2" in url

    # optional params are omitted when not provided
    minimal = _job_logs_ws_url("ts-abc", "job-1", follow=False, tail=None, rank=None)
    assert "follow=false" in minimal
    assert "tail=" not in minimal
    assert "rank=" not in minimal


class _FakeWebSocket:
    """Minimal stand-in for a websocket-client connection."""

    def __init__(self, frames):
        self._frames = list(frames)
        self.closed = False

    def recv(self):
        if not self._frames:
            return ""  # empty frame signals the server closed the stream
        item = self._frames.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        self.closed = True


def _install_fake_websocket(mocker, connections):
    """Register a fake ``websocket`` module whose ``create_connection`` returns the given connections."""
    module = types.ModuleType("websocket")

    # names mirror websocket-client exactly, since stream_logs imports them by name
    class WebSocketConnectionClosedException(Exception):  # noqa: N818
        pass

    class WebSocketTimeoutException(Exception):  # noqa: N818
        pass

    module.WebSocketConnectionClosedException = WebSocketConnectionClosedException
    module.WebSocketTimeoutException = WebSocketTimeoutException
    module.create_connection = mock.MagicMock(side_effect=list(connections))

    mocker.patch.dict(sys.modules, {"websocket": module})
    return module


def test_stream_logs_yields_lines_and_stops(mocker, mocker_auth):
    mocker.patch("lightning_sdk.api.job_api.Auth")
    frame = json.dumps([{"message": "line-1"}, {"message": "line-2"}])
    module = _install_fake_websocket(mocker, [_FakeWebSocket([frame])])

    job_api = JobApiV2()
    lines = list(job_api.stream_logs("job-1", "ts-abc", follow=False))

    assert lines == ["line-1", "line-2"]
    # no reconnect when follow is off -> exactly one connection
    assert module.create_connection.call_count == 1


def test_stream_logs_passes_timestamps_flag(mocker, mocker_auth):
    mocker.patch("lightning_sdk.api.job_api.Auth")
    frame = json.dumps([{"message": "hi", "timestamp": {"seconds": 0, "nanos": 0}}])
    _install_fake_websocket(mocker, [_FakeWebSocket([frame])])

    job_api = JobApiV2()
    lines = list(job_api.stream_logs("job-1", "ts-abc", follow=False, timestamps=True))

    assert lines == ["1970-01-01T00:00:00+00:00 hi"]


def test_stream_logs_reconnects_on_transient_drop(mocker, mocker_auth):
    mocker.patch("lightning_sdk.api.job_api.Auth")

    module_holder = {}

    def _closed_exc():
        return module_holder["module"].WebSocketConnectionClosedException()

    # first connection yields a line then drops; second connection yields another line then ends
    first = _FakeWebSocket([json.dumps([{"message": "before-drop"}])])
    second = _FakeWebSocket([json.dumps([{"message": "after-reconnect"}])])
    module = _install_fake_websocket(mocker, [first, second])
    module_holder["module"] = module
    # make the first connection drop after its frame
    first._frames.append(_closed_exc())

    # stop the loop after the second connection by raising out of the reconnect backoff
    class _StopLoopError(Exception):
        pass

    mocker.patch("lightning_sdk.api.job_api.time.sleep", side_effect=[None, _StopLoopError()])

    job_api = JobApiV2()
    collected = []

    def _drain() -> None:
        for line in job_api.stream_logs("job-1", "ts-abc", follow=True):
            collected.append(line)

    with pytest.raises(_StopLoopError):
        _drain()

    assert collected == ["before-drop", "after-reconnect"]
    assert module.create_connection.call_count == 2
