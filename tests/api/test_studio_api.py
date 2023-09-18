import pytest
from lightning_cloud.openapi import V1CloudSpace, V1GetCloudSpaceInstanceStatusResponse

from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.machine import Machine


def test_get_studio(internal_studio_api_mocker_get_studio):
    studio_api = StudioApi()
    studio = studio_api.get_studio("st-abc", "ts-abc")
    assert isinstance(studio, V1CloudSpace)


def test_get_studio_error(internal_studio_api_mocker_get_studio):
    studio_api = StudioApi()
    with pytest.raises(ValueError, match="Studio xyz does not exist"):
        studio_api.get_studio("xyz", "ts-abc")


@pytest.mark.parametrize("cluster", (None, "c-abc"))
def test_create_studio(internal_studio_api_mocker_create_studio, cluster):
    studio_api = StudioApi()
    studio = studio_api.create_studio("st-abc", "ts-abc", cluster=cluster)
    assert isinstance(studio, V1CloudSpace)
    assert studio.cluster_id == cluster


def test_get_studio_status(internal_studio_api_mocker_studio_status):
    studio_api = StudioApi()
    status = studio_api.get_studio_status("st-abc", "ts-abc")
    assert isinstance(status, V1GetCloudSpaceInstanceStatusResponse)


@pytest.mark.parametrize(
    "machine",
    (
        Machine.CPU,
        Machine.DATA_PREP,
        Machine.T4,
        Machine.T4_X_4,
        Machine.V100,
        Machine.V100_X_4,
        Machine.A10G,
        Machine.A10G_X_4,
        Machine.A100_X_8,
    ),
)
def test_switch_studio_machine(internal_studio_api_mocker_switch_machine, machine):
    studio_api = StudioApi()
    studio_api.switch_studio_machine("st-abc", "ts-abc", machine)


def test_switch_studio_machine_wrong_machine(internal_studio_api_mocker_switch_machine):
    studio_api = StudioApi()

    with pytest.raises(KeyError, match="foo"):
        studio_api.switch_studio_machine("st-abc", "ts-abc", "foo")


def test_start_studio(internal_studio_api_mocker_start_studio):
    studio_api = StudioApi()
    studio_api.start_studio("st-abc", "ts-abc")


def test_stop_studio(internal_studio_api_mocker_stop_studio):
    studio_api = StudioApi()
    studio_api.stop_studio("st-abc", "ts-abc")


def test_run_command(internal_studio_api_mocker_run_command):
    studio_api = StudioApi()

    outputs = studio_api.run_studio_commands("st-abc", "ts-abc", "foo", "bar")
    assert "".join(outputs) == "foo-response bar-response"


def test_delete_studio(internal_studio_api_mocker_delete):
    studio_api = StudioApi()

    studio_api.delete_studio("st-abc", "ts-abc")


@pytest.mark.parametrize(
    "name,expected_machine",
    [
        ("st-abc", Machine.CPU),
        ("st-def", Machine.DATA_PREP),
        ("st-ghi", Machine.T4),
        ("st-jkl", Machine.T4_X_4),
        ("st-mno", Machine.V100),
        ("st-pqr", Machine.V100_X_4),
        ("st-stu", Machine.A10G),
        ("st-vwx", Machine.A10G_X_4),
        ("st-yza", Machine.A100_X_8),
    ],
)
def test_get_machine(internal_studio_api_mocker_get_machine, name, expected_machine):
    studio_api = StudioApi()

    machine = studio_api.get_machine(name, "ts-abc")

    assert isinstance(machine, Machine)
    assert expected_machine == machine

def test_duplicate_user(internal_studio_api_mocker_duplicate_user):
    studio_api = StudioApi()
    kwargs = studio_api.duplicate_studio("st-abc", "ts-abc", "ts-abc")

    assert kwargs == {"name": "st-abc-de", "teamspace": "teamspace-abc", "user": "user-abc"}

def test_duplicate_org(internal_studio_api_mocker_duplicate_org):
    studio_api = StudioApi()
    kwargs = studio_api.duplicate_studio("st-abc", "ts-abc", "ts-abc")

    assert kwargs == {"name": "st-abc-de", "teamspace": "teamspace-abc", "org": "org-abc"}
