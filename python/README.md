# Lightning SDK

Software Development Kit (SDK) for Lightning AI

## Installation

The package can be installed using `pip install lightning-sdk`

## Usage

To use the SDK, you need to export the environment variables `LIGHTNING_USER_ID` and `LIGHTNING_API_KEY` with the values found in your account settings -> Keys -> Programmatic Login.

If you want to use it from within a Studio, these variables are already available for you.

## Deployment CLI

Deployment commands are available through the SDK CLI. The examples below use
`uvx lightning-sdk`, but the same arguments work with `lightning`.

```bash
export LIGHTNING_USER_ID="..."
export LIGHTNING_API_KEY="..."
lightning login
```

Create an `nginx:latest` deployment:

```bash
uvx lightning-sdk deployment create nginx-demo \
  --teamspace owner/teamspace \
  --image nginx:latest \
  --machine CPU \
  --port 80 \
  --replicas 1 \
  --api-key-auth
```

Example output:

```text
Created deployment nginx-demo.
```

List deployments with replica status:

```bash
uvx lightning-sdk deployment list --teamspace owner/teamspace
```

Example output:

```text
Name         Teamspace        State    Replicas  Machine  Image         Cloud account
nginx-demo   owner/teamspace  RUNNING  1/1       cpu-4    nginx:latest  lightning-public-prod
```

Inspect one deployment, including the replica jobs:

```bash
uvx lightning-sdk deployment inspect nginx-demo --teamspace owner/teamspace --jobs
```

Example output:

```json
{
  "current_state": "DEPLOYMENT_STATE_RUNNING",
  "id": "dep_0123456789abcdef",
  "jobs": [
    {
      "id": "job_0123456789abcdef",
      "name": "nginx-demo-0",
      "state": "running"
    }
  ],
  "name": "nginx-demo",
  "replicas": 1
}
```

Update a deployment:

```bash
uvx lightning-sdk deployment update nginx-demo \
  --teamspace owner/teamspace \
  --new-name nginx-demo-v2 \
  --replicas 2
```

Example output:

```text
Updated deployment nginx-demo-v2.
```

Get logs for a deployment by name or ID:

```bash
uvx lightning-sdk deployment logs nginx-demo-v2 --teamspace owner/teamspace
```

Example output:

```text
server started on port 80
GET /health 200
```

If persisted log pages have not been produced yet, the command also checks the
live websocket log stream for recent lines.

Get logs for a specific job in that deployment:

```bash
uvx lightning-sdk deployment logs nginx-demo-v2 \
  --teamspace owner/teamspace \
  --job-id job_0123456789abcdef
```

Example output:

```text
server started on port 80
GET /predict 200
```

Follow live logs:

```bash
uvx lightning-sdk deployment logs nginx-demo-v2 --teamspace owner/teamspace --follow
```

Example output:

```text
server started on port 80
GET /health 200
GET /predict 200
```

Delete a deployment:

```bash
uvx lightning-sdk deployment delete nginx-demo-v2 --teamspace owner/teamspace --yes
```

Example output:

```text
Deleted deployment nginx-demo-v2.
```

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
