from unittest import mock

import pytest

from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1CloudSpaceInstanceStatus,
    V1CloudSpaceInstanceStartupStatus,
    V1StartCloudSpaceInstanceResponse,
)
from lightning_sdk.lightning_cloud.openapi import (
    V1CloudSpaceInstanceState as State,
)
from lightning_sdk.lightning_cloud.openapi import (
    V1GetCloudSpaceInstanceStatusResponse as Status,
)
from lightning_sdk.machine import Machine


def instance(instance_id="new", phase=State.PENDING, message=None, ready=False):
    return Externalv1CloudSpaceInstanceStatus(
        cloud_space_instance_id=instance_id,
        phase=phase,
        status_message=message,
        startup_status=V1CloudSpaceInstanceStartupStatus(top_up_restore_finished=ready),
    )


@pytest.fixture()
def start_api(mocker):
    mocker.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
    api = StudioApi()
    api._client = mock.MagicMock()
    api._client.cloud_space_service_start_cloud_space_instance.return_value = V1StartCloudSpaceInstanceResponse()
    sleep = mocker.patch("lightning_sdk.api.studio_api.time.sleep")
    return api, sleep


@pytest.mark.parametrize("phase", [State.FAILED, State.STOPPING, State.STOPPED, State.DELETED])
@pytest.mark.parametrize("first_poll", [True, False])
def test_start_raises_on_terminal_instance(start_api, phase, first_poll):
    api, sleep = start_api
    statuses = [Status(in_use=instance("old", State.STOPPED))]
    if not first_poll:
        statuses.append(Status(in_use=instance()))
    statuses.append(Status(in_use=instance(phase=phase, message="workload exited (status code: 2)")))
    api._client.cloud_space_service_get_cloud_space_instance_status.side_effect = statuses

    with pytest.raises(RuntimeError, match=f"instance new, {phase}.*workload exited.*2"):
        api.start_studio("studio", "teamspace", Machine.CPU)

    assert sleep.call_count == (0 if first_poll else 1)
    assert api._client.cloud_space_service_get_cloud_space_instance_status.call_count == len(statuses)


def test_start_waits_for_new_instance_and_in_use_readiness(start_api):
    api, sleep = start_api
    old = instance("old", State.DELETED, "previous failure", ready=True)
    statuses = [
        Status(in_use=old),
        Status(in_use=old),
        Status(),
        Status(in_use=old, requested=instance(ready=True)),
        Status(in_use=instance(phase=State.RUNNING, ready=True)),
    ]
    api._client.cloud_space_service_get_cloud_space_instance_status.side_effect = statuses

    api.start_studio("studio", "teamspace", Machine.CPU)

    assert sleep.call_count == 3
    assert api._client.cloud_space_service_get_cloud_space_instance_status.call_count == len(statuses)


@pytest.mark.parametrize("final_status", [Status(), Status(in_use=instance("other", State.RUNNING, ready=True))])
def test_start_raises_if_observed_instance_disappears(start_api, final_status):
    api, sleep = start_api
    api._client.cloud_space_service_get_cloud_space_instance_status.side_effect = [
        Status(),
        Status(requested=instance(message="last observed diagnostic")),
        final_status,
    ]

    with pytest.raises(RuntimeError, match="instance new.*last observed diagnostic"):
        api.start_studio("studio", "teamspace", Machine.CPU)
    sleep.assert_called_once_with(1)


def test_start_reports_terminal_phase_without_message(start_api):
    api, _ = start_api
    api._client.cloud_space_service_get_cloud_space_instance_status.side_effect = [
        Status(),
        Status(in_use=instance(phase=State.STOPPING, ready=True)),
    ]
    with pytest.raises(RuntimeError, match="STOPPING.*stopped before becoming ready"):
        api.start_studio("studio", "teamspace", Machine.CPU)


def test_start_accepts_healthy_running_instance(start_api):
    api, sleep = start_api
    api._client.cloud_space_service_get_cloud_space_instance_status.return_value = Status(
        in_use=instance(phase=State.RUNNING, ready=True)
    )
    api.start_studio("studio", "teamspace", Machine.CPU)
    sleep.assert_not_called()


def test_start_accepts_same_instance_in_requested_and_in_use(start_api):
    api, sleep = start_api
    api._client.cloud_space_service_get_cloud_space_instance_status.return_value = Status(
        requested=instance(), in_use=instance(phase=State.RUNNING, ready=True)
    )
    api.start_studio("studio", "teamspace", Machine.CPU)
    sleep.assert_not_called()


def test_start_waits_through_missing_status(start_api):
    api, sleep = start_api
    api._client.cloud_space_service_get_cloud_space_instance_status.side_effect = [
        None,
        None,
        Status(in_use=instance()),
        None,
        Status(in_use=instance(phase=State.RUNNING, ready=True)),
    ]
    api.start_studio("studio", "teamspace", Machine.CPU)
    assert sleep.call_count == 3


@pytest.mark.parametrize("status", [None, Status(), Status(in_use=Externalv1CloudSpaceInstanceStatus())])
def test_readiness_helper_handles_missing_status(start_api, status):
    api, _ = start_api
    getter = api._client.cloud_space_service_get_cloud_space_instance_status
    getter.return_value = status
    assert not api._check_code_status_top_up_restore_finished("studio", "teamspace")
    getter.assert_called_once()
