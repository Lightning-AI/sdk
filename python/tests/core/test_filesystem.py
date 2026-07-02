from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

import pytest

from lightning_sdk.api.sandbox_api import CommandResult
from lightning_sdk.lightning_cloud.openapi import V1Sandbox
from lightning_sdk.sandbox import WriteFileParams
from lightning_sdk.sandbox.base import SandboxInstance


def _v1(**kwargs) -> V1Sandbox:
    defaults: dict = {
        "id": "sb-fs",
        "name": "n",
        "status": "running",
        "organization_id": "org-1",
        "instance_type": "cpu.small",
        "spot": False,
        "ports": [],
        "cluster_id": "",
        "cloudspace_id": "",
    }
    defaults.update(kwargs)
    return V1Sandbox(**defaults)


def test_fs_property_returns_cached_filesystem():
    mock_api = mock.MagicMock()
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)
    assert sb.fs is sb.fs


def test_write_file_path_and_content():
    mock_api = mock.MagicMock()
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)
    sb.write_file = mock.MagicMock()

    sb.fs.write_file("/a.txt", "hello")

    sb.write_file.assert_called_once_with("/a.txt", "hello")


def test_write_file_write_file_params():
    mock_api = mock.MagicMock()
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)
    sb.write_file = mock.MagicMock()

    sb.fs.write_file(WriteFileParams(path="/b.txt", content="yo"))

    sb.write_file.assert_called_once_with("/b.txt", "yo")


def test_exists_true_and_false():
    mock_api = mock.MagicMock()
    mock_api.run_command.side_effect = [
        CommandResult(cmd_id="", output="", exit_code=0),
        CommandResult(cmd_id="", output="", exit_code=1),
    ]
    sb = SandboxInstance(_v1(organization_id="org-1"), sandbox_api=mock_api)

    assert sb.fs.exists("/x") is True
    assert sb.fs.exists("/missing") is False
    assert mock_api.run_command.call_args_list[0].kwargs["command"] == "test"
    assert mock_api.run_command.call_args_list[0].kwargs["args"] == ["-e", "/x"]


def test_stat_parses_output():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(
        cmd_id="c",
        output="regular file|1024|1715000000|644\n",
        exit_code=0,
    )
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)

    st = sb.fs.stat("/a/b")

    assert st.file_type == "regular file"
    assert st.size == 1024
    assert st.mode == "644"
    assert st.mtime == datetime.fromtimestamp(1715000000, tz=timezone.utc)
    mock_api.run_command.assert_called_once_with(
        "sb-fs",
        command="stat",
        args=["--format=%F|%s|%Y|%a", "/a/b"],
        organization_id="org-1",
    )


def test_stat_raises_on_command_failure():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="", output="err\n", exit_code=1)
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)

    with pytest.raises(RuntimeError, match=r"stat /nope failed \(exit 1\)"):
        sb.fs.stat("/nope")


def test_stat_raises_on_bad_shape():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="", output="oops\n", exit_code=0)
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)

    with pytest.raises(RuntimeError, match="unexpected stat output"):
        sb.fs.stat("/x")


def test_readdir():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(
        cmd_id="",
        output=".hidden\na\nb\n\n",
        exit_code=0,
    )
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)

    assert sb.fs.readdir("/d") == [".hidden", "a", "b"]


def test_readdir_raises_when_ls_fails():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="", output="ls: bad\n", exit_code=2)
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)

    with pytest.raises(RuntimeError, match=r"readdir /bad failed \(exit 2\)"):
        sb.fs.readdir("/bad")


def test_rm_and_rm_recursive():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="", output="", exit_code=0)
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)

    sb.fs.rm("/f")
    sb.fs.rm("/tree", recursive=True)

    calls = mock_api.run_command.call_args_list
    assert calls[0].kwargs["command"] == "rm"
    assert calls[0].kwargs["args"] == ["/f"]
    assert calls[1].kwargs["args"] == ["-rf", "/tree"]


def test_rm_raises():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="", output="no\n", exit_code=1)
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)

    with pytest.raises(RuntimeError, match=r"rm /ro failed \(exit 1\)"):
        sb.fs.rm("/ro")


def test_mkdir_and_mkdir_recursive():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="", output="", exit_code=0)
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)

    sb.fs.mkdir("/d")
    sb.fs.mkdir("/a/b/c", recursive=True)

    calls = mock_api.run_command.call_args_list
    assert calls[0].kwargs["command"] == "mkdir"
    assert calls[0].kwargs["args"] == ["/d"]
    assert calls[1].kwargs["args"] == ["-p", "/a/b/c"]


def test_mkdir_raises():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="", output="exists\n", exit_code=1)
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)

    with pytest.raises(RuntimeError, match=r"mkdir /d failed \(exit 1\)"):
        sb.fs.mkdir("/d")


def test_rename_copy_symlink():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="", output="", exit_code=0)
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)

    sb.fs.rename("/o", "/n")
    sb.fs.copy_file("/s", "/d")
    sb.fs.symlink("/t", "/l")

    calls = [c.kwargs for c in mock_api.run_command.call_args_list]
    assert calls[0]["command"] == "mv"
    assert calls[0]["args"] == ["/o", "/n"]
    assert calls[1]["command"] == "cp"
    assert calls[1]["args"] == ["/s", "/d"]
    assert calls[2]["command"] == "ln"
    assert calls[2]["args"] == ["-s", "/t", "/l"]


def test_chmod_number_and_string():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="", output="", exit_code=0)
    sb = SandboxInstance(_v1(), sandbox_api=mock_api)

    sb.fs.chmod("/f", 0o755)
    sb.fs.chmod("/g", "644")

    calls = mock_api.run_command.call_args_list
    assert calls[0].kwargs["args"] == ["755", "/f"]
    assert calls[1].kwargs["args"] == ["644", "/g"]
