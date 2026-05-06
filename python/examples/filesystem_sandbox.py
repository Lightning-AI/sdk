"""Exercise every :class:`~lightning_sdk.sandbox.filesystem.FileSystem` helper against a real sandbox.

Prerequisites:
  - Python 3.10+
  - API credentials (``LIGHTNING_SANDBOX_API_KEY`` or `lightning login` / stored credentials)

Usage (from the ``python/`` directory)::

  LIGHTNING_SANDBOX_API_KEY=... python examples/filesystem_sandbox.py

Optional environment variables:
  - ``LIGHTNING_CLOUD_URL`` — non-default cloud host
  - ``LIGHTNING_ORG_ID`` — if your key needs org scope (use :meth:`SandboxInstance.configure`)
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

from lightning_sdk.sandbox import SandboxInstance, WriteFileParams
from lightning_sdk.sandbox.filesystem import FileSystem

INSTANCE_TYPE = "cpu-1"


def log(phase: str, detail: Any = None) -> None:
    print(f"\n--- {phase} ---")
    if detail is not None:
        print(detail)


def assert_path_removed(fs: FileSystem, path: str) -> None:
    if fs.exists(path):
        raise AssertionError(f"expected path to be gone after rm: {path}")
    print("removed ok:", path)


def main() -> None:
    # org_id = os.environ.get("LIGHTNING_ORG_ID")
    # base_url = os.environ.get("LIGHTNING_CLOUD_URL")
    # cfg: dict[str, str] = {}
    # if org_id:
    #     cfg["organization_id"] = org_id
    # if base_url:
    #     cfg["base_url"] = base_url
    # if cfg:
    SandboxInstance.configure(api_key="sk-lit-a749db8f-e049-4781-8012-a45258c6e1c7")

    ts = int(time.time() * 1000)
    base = f"/tmp/sdk-fs-demo-{ts}"

    sandbox = SandboxInstance.create(
        name=f"fs-demo-{ts}",
        instance_type=INSTANCE_TYPE,
    )
    log("Sandbox ready", sandbox.sandbox_id)

    fs = sandbox.fs

    sandbox.run_command("mkdir", ["-p", base])
    sandbox.run_command("mkdir", ["-p", f"{base}/nested"])

    log("write_file (path + string)")
    fs.write_file(f"{base}/hello.txt", "hello from sdk-fs\n")

    log("write_file (WriteFileParams)")
    fs.write_file(WriteFileParams(path=f"{base}/nested/note.txt", content="nested note\n"))

    log("exists (true)")
    print(fs.exists(f"{base}/hello.txt"))

    log("exists (false)")
    print(fs.exists(f"{base}/missing.txt"))

    log("stat (file)")
    st = fs.stat(f"{base}/hello.txt")
    print(
        {
            "file_type": st.file_type,
            "size": st.size,
            "mode": st.mode,
            "mtime": st.mtime.isoformat(),
        }
    )

    log("readdir")
    entries = fs.readdir(base)
    print(sorted(entries))

    log("copy_file")
    fs.copy_file(f"{base}/hello.txt", f"{base}/hello-copy.txt")
    print("copy exists:", fs.exists(f"{base}/hello-copy.txt"))

    log("rename")
    fs.rename(f"{base}/hello-copy.txt", f"{base}/renamed.txt")
    print("renamed exists:", fs.exists(f"{base}/renamed.txt"))
    print("old copy path exists:", fs.exists(f"{base}/hello-copy.txt"))

    log("chmod (octal number → chmod argv)")
    fs.chmod(f"{base}/renamed.txt", 0o600)
    st_after_chmod = fs.stat(f"{base}/renamed.txt")
    print("mode after chmod 600:", st_after_chmod.mode)

    fs.chmod(f"{base}/renamed.txt", "644")
    print("mode after chmod string 644:", fs.stat(f"{base}/renamed.txt").mode)

    log("symlink")
    fs.symlink(f"{base}/hello.txt", f"{base}/link-to-hello")
    print("symlink exists:", fs.exists(f"{base}/link-to-hello"))

    log(
        "stat (symlink path — may report the link itself or the target depending on stat(1) in the image)"
    )
    print(fs.stat(f"{base}/link-to-hello"))

    log("rm (file)")
    fs.rm(f"{base}/link-to-hello")
    assert_path_removed(fs, f"{base}/link-to-hello")

    log("rm (recursive=True)")
    fs.rm(f"{base}/nested", recursive=True)
    assert_path_removed(fs, f"{base}/nested")

    log("cleanup tree")
    fs.rm(base, recursive=True)
    assert_path_removed(fs, base)

    sandbox.delete()
    log("Sandbox deleted")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(err, file=sys.stderr)
        raise SystemExit(1) from err
