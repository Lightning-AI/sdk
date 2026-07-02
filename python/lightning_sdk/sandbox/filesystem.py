from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from lightning_sdk.sandbox.base import SandboxInstance, WriteFileParams
from lightning_sdk.sandbox.command import Command


def _assert_command_ok(r: Command, what: str) -> None:
    if r.exit_code == 0:
        return
    tail = r.output.strip()
    msg = f"{what} failed (exit {r.exit_code})"
    if tail:
        msg += f": {tail}"
    raise RuntimeError(msg)


@dataclass(frozen=True)
class FileStat:
    """Metadata from GNU ``stat --format`` (see :meth:`FileSystem.stat`)."""

    file_type: str
    size: int
    mtime: datetime
    mode: str


class FileSystem:
    """Filesystem helpers that run inside the sandbox via shell commands.

    Use :attr:`~lightning_sdk.sandbox.base.SandboxInstance.fs` on a sandbox instance.
    """

    def __init__(self, sandbox: SandboxInstance) -> None:
        self._sandbox = sandbox

    def write_file(
        self,
        path_or_params: str | WriteFileParams,
        content: str | None = None,
    ) -> None:
        """Write file content via the sandbox files API (same as :meth:`SandboxInstance.write_file`)."""
        if isinstance(path_or_params, WriteFileParams):
            self._sandbox.write_file(path_or_params.path, path_or_params.content)
        else:
            self._sandbox.write_file(path_or_params, content or "")

    def exists(self, path: str) -> bool:
        r = self._sandbox.run_command("test", ["-e", path])
        return r.exit_code == 0

    def stat(self, path: str) -> FileStat:
        r = self._sandbox.run_command("stat", ["--format=%F|%s|%Y|%a", path])
        _assert_command_ok(r, f"stat {path}")
        line = r.output.strip()
        parts = line.split("|")
        if len(parts) < 4:
            raise RuntimeError(f"unexpected stat output for {path}: {line}")
        file_type, size_str, mtime_sec_str, mode = parts[:4]
        mtime_sec = int(mtime_sec_str)
        return FileStat(
            file_type=file_type,
            size=int(size_str),
            mtime=datetime.fromtimestamp(mtime_sec, tz=timezone.utc),
            mode=mode,
        )

    def readdir(self, path: str) -> list[str]:
        r = self._sandbox.run_command("ls", ["-1A", path])
        _assert_command_ok(r, f"readdir {path}")
        return [line for line in r.output.split("\n") if line]

    def rm(self, path: str, *, recursive: bool = False) -> None:
        args = ["-rf", path] if recursive else [path]
        r = self._sandbox.run_command("rm", args)
        _assert_command_ok(r, f"rm {path}")

    def mkdir(self, path: str, *, recursive: bool = False) -> None:
        args = ["-p", path] if recursive else [path]
        r = self._sandbox.run_command("mkdir", args)
        _assert_command_ok(r, f"mkdir {path}")

    def rename(self, old_path: str, new_path: str) -> None:
        r = self._sandbox.run_command("mv", [old_path, new_path])
        _assert_command_ok(r, f"rename {old_path} -> {new_path}")

    def copy_file(self, src: str, dest: str) -> None:
        r = self._sandbox.run_command("cp", [src, dest])
        _assert_command_ok(r, f"copy_file {src} -> {dest}")

    def chmod(self, path: str, mode: str | int) -> None:
        m = format(mode, "o") if isinstance(mode, int) else mode
        r = self._sandbox.run_command("chmod", [m, path])
        _assert_command_ok(r, f"chmod {path}")

    def symlink(self, target: str, path: str) -> None:
        r = self._sandbox.run_command("ln", ["-s", target, path])
        _assert_command_ok(r, f"symlink {path}")
