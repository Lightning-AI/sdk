from contextlib import nullcontext

import pytest

from lightning_sdk.machine import Machine
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio


@pytest.mark.parametrize("create_ok", [True, False])
@pytest.mark.parametrize("cluster", [None, "c-abc"])
@pytest.mark.parametrize("name", ["st-abc", "st-xyz"])
def test_studio_init(internal_studio_init_mocker, name, cluster, create_ok):
    # st-xyz does not exist and should not be created
    error_out = bool(name == "st-xyz" and not create_ok)
    contextman = pytest.raises(ValueError, match="Studio st-xyz does not exist") if error_out else nullcontext()

    with contextman:
        studio = Studio(name=name, teamspace="ts-abc", org="org-abc", cluster=cluster, create_ok=create_ok)

    if error_out:
        return

    assert studio.teamspace == "ts-abc"
    assert studio.owner == "org-abc"
    assert studio.name == name


@pytest.mark.parametrize(
    ("name", "expected_status"),
    [
        ("st-abc", Status.Pending),
        ("st-def", Status.Pending),
        ("st-ghi", Status.Running),
        ("st-jkl", Status.Failed),
        ("st-mno", Status.Stopping),
        ("st-pqr", Status.Stopped),
        ("st-stu", Status.Stopped),
    ],
)
def test_studio_status(internal_studio_status_mocker, internal_studio_init_mocker, name, expected_status):
    studio = Studio(name=name, teamspace="ts-abc", org="org-abc", create_ok=True)
    assert studio.status == expected_status


def test_studio_start(internal_studio_start_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    assert studio.status == Status.Stopped
    assert studio.machine is None

    studio.start()

    assert studio.status == Status.Running
    assert studio.machine is not None


def test_studio_stop(internal_studio_stop_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    assert studio.status == Status.Running

    studio.stop()

    assert studio.status == Status.Stopped


def test_studio_delete(internal_studio_delete_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc", create_ok=False)

    studio.delete()

    # doesn't exist anymore when deleted
    with pytest.raises(ValueError, match="Studio st-abc does not exist"):
        Studio(name="st-abc", teamspace="ts-abc", org="org-abc", create_ok=False)


@pytest.mark.parametrize(
    "target_machine",
    [
        Machine.CPU,
        Machine.DATA_PREP,
        Machine.T4,
        Machine.T4_X_4,
        Machine.V100,
        Machine.V100_X_4,
        Machine.A10G,
        Machine.A10G_X_4,
        Machine.A100_X_8,
    ],
)
def test_studio_switch_machine(internal_studio_switch_mocker, internal_studio_init_mocker, target_machine):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    assert studio.machine is None
    print(studio.teamspace)
    studio.start()

    assert studio.machine == Machine.CPU
    studio.switch_machine(target_machine)

    assert studio.machine == target_machine


def test_run_command(internal_studio_init_mocker, internal_studio_run_mocker):
    studio = Studio("st-abc", "ts-abc", "org-abc")

    result = studio.run("foo", "bar")

    assert result == "foo-response bar-response"


@pytest.mark.parametrize(
    ("name", "expected_state", "forbidden_actions"),
    [
        ("st-def", Status.Pending, ["start", "switch", "run"]),
        ("st-ghi", Status.Running, ["start"]),
        ("st-jkl", Status.Failed, ["start", "stop", "switch", "run"]),
        ("st-mno", Status.Stopping, ["start", "switch", "run", "stop"]),
        ("st-pqr", Status.Stopped, ["stop", "switch", "run"]),
    ],
)
def test_action_in_wrong_state(
    internal_studio_init_mocker, internal_studio_status_mocker, name, expected_state, forbidden_actions
):
    studio = Studio(name, "ts-abc", "org-abc")
    assert studio.status == expected_state

    if "start" in forbidden_actions:
        with pytest.raises(
            RuntimeError, match=f"Cannot start a studio that is not stopped. Studio {name} is {expected_state}."
        ):
            studio.start()

    if "switch" in forbidden_actions:
        with pytest.raises(
            RuntimeError,
            match=f"Cannot switch machine on a studio that is not running. Studio {name} is {expected_state}.",
        ):
            studio.switch_machine(Machine.A10G)

    if "run" in forbidden_actions:
        with pytest.raises(
            RuntimeError,
            match=f"Cannot run a command in a studio that is not running. Studio {name} is {expected_state}.",
        ):
            studio.run("foo")

    if "stop" in forbidden_actions:
        with pytest.raises(
            RuntimeError, match=f"Cannot stop a studio that is not running. Studio {name} is {expected_state}"
        ):
            studio.stop()
