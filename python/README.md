# Lightning SDK

Software Development Kit (SDK) for Lightning AI

## Installation

The package can be installed using `pip install lightning-sdk`

## Usage

To use the SDK, you need to export the environment variables `LIGHTNING_USER_ID` and `LIGHTNING_API_KEY` with the values found in your account settings -> Keys -> Programmatic Login.

If you want to use it from within a Studio, these variables are already available for you.

## Example

```python
from lightning_sdk import Machine, Studio

# or s =  Studio("my-studio", "my-teamspace", org="my-org", create_ok=True)
# or (inside a Studio) s = Studio()  # will infer name, teamspace and owner of the current studio automatically.
#    can also just pass some arguments: s = Studio("my-new-studio", create_ok=True)
s = Studio("my-studio", "my-teamspace", user="my-username", create_ok=True)

print("starting Studio...")
s.start()

# prints Machine.CPU-4
print(s.machine)

# or start directly on this machine with s.start(Machine.L4)
print("switching Studio machine...")
s.switch_machine(Machine.L4)

# prints Machine.L4
print(s.machine)

# prints Status.Running
print(s.status)

print(s.run("nvidia-smi"))

# install plugins for jobs and multi-machine training
s.install_plugin("jobs")
s.install_plugin("multi-machine-training")

# run the resulting plugins to start 1 job and 1 multi-machine training
s.installed_plugins["jobs"].run("python my_dummy_file", name="my_first_job", machine=Machine.L4)
s.installed_plugins["multi-machine-training"].run("python my_dummy_file", name="my_first_mmt", machine=Machine.T4, num_instances=42)

print("Stopping Studio")
s.stop()

# duplicates Studio, this will also duplicate the environment and all files in the Studio
duplicate = s.duplicate()

# delete original Studio, duplicated Studio is it's own entity and not related to original anymore
s.delete()

# stop and delete duplicated Studio
duplicate.stop()
duplicate.delete()
```

## Sandbox PTY sessions

For interactive shells (REPLs, build watchers, anything that needs `stdin` /
window-resize / ANSI), use the `sandbox.process` namespace instead of
`run_command`. PTY sessions are bridged over a WebSocket from the controlplane
down to the in-sandbox SSH server, with the same xterm wire protocol the
Lightning UI's web terminal uses.

PTY support requires the `websocket-client` package (installed automatically
with `lightning-sdk`).

### Create a session

```python
from lightning_sdk.sandbox import Sandbox, PtyCreateOpts

sandbox = Sandbox().create(name="pty-example", instance_type="cpu-2")

pty = sandbox.process.create_pty(
    PtyCreateOpts(
        session_name="build",
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

pty.wait_for_connection()
pty.send_input("uname -a\n")
pty.send_input("exit\n")

result = pty.wait()
print(f"exit code: {result.exit_code}")
```

To capture output programmatically instead of streaming it to `sys.stdout`,
pass any callable as `on_data` (e.g. `on_data=chunks.append`). To suppress
output entirely, use `on_data=PtyHandle.discard`.

> **Why a default at all?** `sys.stdout.buffer` is block-buffered (8 KB)
> regardless of TTY status, so a naive `lambda chunk: sys.stdout.buffer.write(chunk)`
> shows nothing until the buffer fills or the process exits. The SDK's
> default flushes per chunk so users get the live-shell experience they'd
> get from the JS SDK on a TTY.

### Reconnect to a session

```python
from lightning_sdk.sandbox import PtyConnectOpts

pty = sandbox.process.connect_pty(
    "build",
    sandbox.cluster_id,
    PtyConnectOpts(on_data=lambda chunk: sys.stdout.buffer.write(chunk)),
)
```

### List, inspect, and kill sessions

```python
sessions = sandbox.process.list_pty_sessions()
for s in sessions:
    print(s.id, s.active, s.cols, s.rows)

info = sandbox.process.get_pty_session_info("build")
sandbox.process.kill_pty_session("build")
```

### Resize

Resize from a handle (preferred — works without a server round-trip):

```python
pty.resize(150, 40)
```

Or via the namespace, which finds the live handle in this process:

```python
sandbox.process.resize_pty_session("build", 150, 40)
```

### `PtyHandle` reference

| Member                              | Description                                              |
| ----------------------------------- | -------------------------------------------------------- |
| `send_input(str \| bytes)`          | Send raw bytes to the shell (e.g. `"\u0003"` for Ctrl+C) |
| `resize(cols, rows)`                | Send a resize control frame                              |
| `wait(timeout=None)`                | Block until the WebSocket closes; returns `PtyResult`    |
| `wait_for_connection(timeout=None)` | Block until the WebSocket opens                          |
| `kill()`                            | Send Ctrl+C and disconnect                               |
| `disconnect()`                      | Close the WebSocket without killing the shell            |
| `is_connected()`                    | Whether the WebSocket is OPEN                            |
| `exit_code`                         | `0` on clean close, `-1` on abnormal, `None` while alive |
| `error`                             | Termination reason on abnormal close, otherwise `None`   |
| `size`                              | Most recent `PtySize(cols=..., rows=...)`                |

> **Note on cross-process persistence.** Within a single SDK process, every
> PTY method works against an in-process registry. Reattaching from a
> *different* process to a session that's still running on the sandbox
> requires the runtime image to ship `screen` (or similar) and the in-sandbox
> SSH login shell to honor `LAI_TERM_SESSION_NAME` / `LAI_TERM_RESTORE` —
> both of which are tracked as a follow-up to this initial parity work. The
> API surface above does not change either way.
