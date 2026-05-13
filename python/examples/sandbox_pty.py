"""Demonstrates the PTY (pseudo-terminal) namespace on a sandbox.

Creating an interactive session, streaming output, sending input, resizing,
and tearing it down. Mirrors ``js/examples/sandbox-pty.ts``.

Requires the ``websocket-client`` package (a regular dependency of
``lightning-sdk``).

Usage (from the ``python/`` directory)::

  LIGHTNING_SANDBOX_API_KEY=... python examples/sandbox_pty.py
"""

from __future__ import annotations

import sys
import time

from lightning_sdk.sandbox import (
    PtyConnectOpts,
    PtyCreateOpts,
    PtyHandle,
    SandboxInstance,
)


def main() -> None:
    sandbox = SandboxInstance.create(
        name=f"pty-example-{int(time.time())}",
        instance_type="cpu-2",
        cluster_id="baremetal",
    )
    print(f"Created sandbox: id={sandbox.sandbox_id} cluster={sandbox.cluster_id}")

    # --- Create an interactive PTY session -------------------------------
    print("\n--- Interactive PTY ---")

    pty = sandbox.process.create_pty(
        PtyCreateOpts(
            session_name="main-default",
            cluster_id=sandbox.cluster_id,
            cwd="/root",
            cols=120,
            rows=30,
            envs={"TERM": "xterm-256color"},
            # `on_data` is omitted: the SDK defaults to `write_to_stdout`,
            # which writes the raw shell bytes to `sys.stdout` and flushes
            # per chunk (mirrors Node's `process.stdout.write` on a TTY).
        )
    )

    # Surface handshake failures fast instead of hanging. Set
    # LIGHTNING_SDK_PTY_DEBUG=1 to see the wire trace if this raises.
    pty.wait_for_connection(timeout=30)
    pty.send_input("uname -a\n")
    pty.send_input("ls -la /\n")

    # Pretend the user just resized their terminal window.
    pty.resize(150, 40)

    # Cleanly exit the shell so .wait() returns.
    pty.send_input("exit\n")

    result = pty.wait()
    print(f"\nPTY closed: exit_code={result.exit_code} error={result.error}")

    # --- Listing / inspecting / killing sessions -------------------------
    print("\n--- Session bookkeeping ---")

    sessions = sandbox.process.list_pty_sessions()
    print(f"Active sessions: {len(sessions)}")
    for s in sessions:
        print(f"  {s.id} active={s.active} {s.cols}x{s.rows or '?'}")

    # Spawn a background loop and demonstrate kill_pty_session.
    # `PtyHandle.discard` opts out of the default stdout sink so the background
    # session's output doesn't interleave with the rest of this script.
    bg = sandbox.process.create_pty(
        PtyCreateOpts(
            session_name="main-background",
            cluster_id=sandbox.cluster_id,
            on_data=PtyHandle.discard,
        )
    )
    bg.wait_for_connection()
    bg.send_input("while true; do echo tick; sleep 1; done\n")
    time.sleep(2)
    sandbox.process.kill_pty_session("main-background")
    print("Killed background session")

    # `connect_pty` reuses an existing session within the same process; the
    # explicit reattach below works once cross-process persistence (`screen`
    # in the runtime image) is wired up.
    _ = PtyConnectOpts  # imported for the README example; suppress F401

    sandbox.delete()
    print("\nSandbox deleted")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(err, file=sys.stderr)
        raise SystemExit(1) from err
