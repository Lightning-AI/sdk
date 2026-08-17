from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

import pytest
from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli
from lightning_sdk.cli.instance import commands as instance_commands
from lightning_sdk.cloud_instance import InstanceImage, InstanceType
from tests.cli.help import assert_help_contains, mock_command_logging


class FakeInstance:
    def __init__(self, instance_id: str = "i-1", name: str = "unit-vm", status: str = "running") -> None:
        self.instance_id = instance_id
        self.instance_name = name
        self.status_value = status
        self.deleted = False
        self.ssh_kwargs: dict | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.instance_id,
            "name": self.instance_name,
            "organization_id": "org-1",
            "cloud_account": "lightning-baremetal",
            "instance_type": "cpu-4",
            "volume_size": 400,
            "spot": False,
            "status": self.status_value,
            "status_reason": "" if self.status_value != "failed" else "out of capacity",
            "region": "dfw1",
            "availability_zone": "",
            "ports": [8080],
            "image": "",
            "ssh_user": "ubuntu",
            "ssh_host": "203.0.113.10",
            "ssh_port": 2201,
            "ssh_command": "ssh -p 2201 ubuntu@203.0.113.10" if self.status_value == "running" else "",
            "user_id": "user-1",
            "created_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "started_at": None,
            "updated_at": None,
        }

    def ssh_args(self, **kwargs) -> list[str]:
        self.ssh_kwargs = kwargs
        return ["ssh", "-i", "/tmp/key", "-p", "2201", "ubuntu@203.0.113.10", *kwargs.get("command", [])]

    def delete(self) -> None:
        self.deleted = True


@pytest.fixture()
def fake_instance():
    """Patch :class:`CloudInstance` in the CLI module with a fake bound to one instance."""
    instance = FakeInstance()
    cls = mock.MagicMock()
    cls.return_value = instance
    cls.create.return_value = instance
    cls.list.return_value = [instance]
    with mock.patch.object(instance_commands, "CloudInstance", cls):
        yield instance, cls


def run(args: list[str]):
    return CliRunner().invoke(main_cli, ["instance", *args], catch_exceptions=False)


@mock_command_logging
def test_create_forwards_every_option(fake_instance, tmp_path):
    instance, cls = fake_instance
    cloud_init = tmp_path / "cloud-init.yaml"
    cloud_init.write_text("#cloud-config\npackages: [nginx]\n")

    result = run(
        [
            "create",
            "unit-vm",
            "-t",
            "cpu-4",
            "--org",
            "my-org",
            "--cloud-account",
            "lightning-baremetal",
            "--volume-size",
            "500",
            "--spot",
            "--port",
            "8080",
            "--port",
            "9090",
            "--image",
            "ubuntu-24.04",
            "--cloud-init",
            str(cloud_init),
            "--wait",
            "--timeout",
            "60",
        ]
    )

    assert result.exit_code == 0, result.output
    assert cls.create.call_args.kwargs == {
        "name": "unit-vm",
        "instance_type": "cpu-4",
        "cloud_account": "lightning-baremetal",
        "org": "my-org",
        "volume_size": 500,
        "spot": True,
        "ports": [8080, 9090],
        "image": "ubuntu-24.04",
        "cloud_init": "#cloud-config\npackages: [nginx]\n",
        "wait": True,
        "timeout": 60.0,
    }
    assert "ssh -p 2201 ubuntu@203.0.113.10" in result.output


@mock_command_logging
def test_create_reads_cloud_init_from_stdin(fake_instance):
    _, cls = fake_instance

    result = CliRunner().invoke(
        main_cli,
        ["instance", "create", "unit-vm", "-t", "cpu-4", "--cloud-init", "-"],
        input="#cloud-config\nruncmd: [echo hi]\n",
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert cls.create.call_args.kwargs["cloud_init"] == "#cloud-config\nruncmd: [echo hi]\n"


@mock_command_logging
def test_create_json_output_is_machine_readable(fake_instance):
    result = run(["create", "unit-vm", "-t", "cpu-4", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["id"] == "i-1"


@mock_command_logging
def test_list_renders_a_table(fake_instance):
    result = run(["list", "--org", "my-org"])

    assert result.exit_code == 0, result.output
    assert "unit-vm" in result.output
    assert "cpu-4" in result.output
    assert fake_instance[1].list.call_args.kwargs == {"org": "my-org"}


@mock_command_logging
def test_list_without_instances(fake_instance):
    _, cls = fake_instance
    cls.list.return_value = []

    result = run(["list"])

    assert result.exit_code == 0, result.output
    assert "No instances found" in result.output


@mock_command_logging
def test_get_shows_the_failure_reason(fake_instance):
    instance, _ = fake_instance
    instance.status_value = "failed"

    result = run(["get", "unit-vm"])

    assert result.exit_code == 0, result.output
    assert "out of capacity" in result.output


@mock_command_logging
def test_delete_requires_confirmation(fake_instance):
    instance, _ = fake_instance

    result = run(["delete", "unit-vm"])

    assert result.exit_code == 1, result.output
    assert instance.deleted is False


@mock_command_logging
def test_delete_with_yes(fake_instance):
    instance, cls = fake_instance

    result = run(["delete", "unit-vm", "--org", "my-org", "-y"])

    assert result.exit_code == 0, result.output
    assert instance.deleted is True
    assert cls.call_args.kwargs == {"org": "my-org"}
    assert "Instance deleted" in result.output


@mock_command_logging
def test_ssh_runs_the_command_on_the_instance(fake_instance):
    instance, _ = fake_instance

    with mock.patch.object(instance_commands.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run_mock:
        result = run(["ssh", "unit-vm", "--", "uname", "-a"])

    assert result.exit_code == 0, result.output
    assert instance.ssh_kwargs == {"command": ["uname", "-a"], "options": []}
    assert run_mock.call_args.args[0][-2:] == ["uname", "-a"]


@mock_command_logging
def test_ssh_propagates_the_remote_exit_code(fake_instance):
    with mock.patch.object(instance_commands.subprocess, "run", return_value=SimpleNamespace(returncode=7)):
        result = run(["ssh", "unit-vm", "--", "false"])

    assert result.exit_code == 7


@mock_command_logging
def test_ssh_print_does_not_connect(fake_instance):
    with mock.patch.object(instance_commands.subprocess, "run") as run_mock:
        result = run(["ssh", "unit-vm", "--print"])

    assert result.exit_code == 0, result.output
    assert "ssh -i /tmp/key -p 2201 ubuntu@203.0.113.10" in result.output
    run_mock.assert_not_called()


@mock_command_logging
def test_images(fake_instance):
    _, cls = fake_instance
    cls.images.return_value = [InstanceImage(name="ubuntu-24.04", description="Ubuntu 24.04 LTS")]

    result = run(["images", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == [{"name": "ubuntu-24.04", "description": "Ubuntu 24.04 LTS"}]


@mock_command_logging
def test_types(fake_instance):
    _, cls = fake_instance
    cls.instance_types.return_value = [InstanceType(name="cpu-4", description="4 CPU, 16 GB RAM", cost=0.33)]

    result = run(["types"])

    assert result.exit_code == 0, result.output
    assert "cpu-4" in result.output
    assert "0.33" in result.output


@mock_command_logging
def test_help_lists_the_lifecycle_commands():
    assert_help_contains(
        "lightning instance --help",
        "create",
        "delete",
        "get",
        "images",
        "list",
        "ssh",
        "types",
    )
