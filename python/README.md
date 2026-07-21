<div align="center">

# Lightning SDK for Python

**Automate Lightning AI resources from Python scripts, notebooks, and CI.**

______________________________________________________________________

<p align="center">
  <a href="#quick-start">Quick start</a> •
  <a href="#examples">Examples</a> •
  <a href="#cli">CLI</a> •
  <a href="#development">Development</a> •
  <a href="https://lightning.ai/docs/overview/sdk-reference">Docs</a>
</p>

[![PyPI](https://img.shields.io/pypi/v/lightning-sdk.svg)](https://pypi.org/project/lightning-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/lightning-sdk.svg)](https://pypi.org/project/lightning-sdk/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](../LICENSE)

</div>

# Why Lightning SDK?

Lightning SDK turns Lightning AI into a Python API. Use it to create and manage
compute, run training or batch jobs, operate persistent studios, deploy
containers, inspect logs, and manage sandboxes without leaving your code.

It is designed for automation first: scripts can resolve teamspace scope, start
machines, wait for work to finish, collect output, and tear resources down in
the same flow.

Build on [Lightning AI](https://lightning.ai), the platform for training,
deploying, and scaling AI applications with managed compute, collaborative
studios, and production endpoints.

# Quick start

Install the package:

```bash
pip install lightning-sdk
```

Authenticate once:

```bash
lightning login
```

Or export credentials from Lightning AI account settings:

```bash
export LIGHTNING_USER_ID="..."
export LIGHTNING_API_KEY="..."
```

Run a sandbox command:

```python
from lightning_sdk.sandbox import Sandbox

sandbox = Sandbox.create(name="python-readme", instance_type="cpu-1")
command = sandbox.run_command("python --version")
print(command.output)
sandbox.delete()
```

Sandbox-only API keys can also be set with `LIGHTNING_SANDBOX_API_KEY` or
passed through `Sandbox.configure(...)`.

# Examples

## Work with a studio

```python
from lightning_sdk import Machine, Studio

studio = Studio("research", teamspace="owner/teamspace", create_ok=True)
studio.start(Machine.CPU)

print(studio.status)
print(studio.run("python --version"))

studio.stop()
```

## Run a container job

```python
from lightning_sdk import Job, Machine

job = Job.run(
    name="batch-job",
    teamspace="owner/teamspace",
    image="python:3.11-slim",
    machine=Machine.CPU,
    command="python -c 'print(\"hello from a Lightning job\")'",
    interruptible=True,
)

job.wait()
print(job.status)
```

## Deploy a container

```python
from lightning_sdk import Deployment, Machine
from lightning_sdk.api.deployment_api import ApiKeyAuth

deployment = Deployment("nginx-demo", teamspace="owner/teamspace")
deployment.start(
    image="nginx:latest",
    machine=Machine.CPU,
    ports=80,
    replicas=1,
    auth=ApiKeyAuth(),
)

print(deployment.status)
```

## Use persistent sandboxes

```python
from lightning_sdk.sandbox import Sandbox

sandbox = Sandbox.create(
    name="persistent-devbox",
    instance_type="cpu-1",
    persistent=True,
)

sandbox.write_file("/workspace/app.py", "print('hello from a file')\n")
print(sandbox.run_command("python /workspace/app.py").output)

snapshot_id = sandbox.stop()
print(snapshot_id)
```

# CLI

The package installs `lightning`, `lightning-sdk`, and `sandbox` commands. The
examples below use `lightning`, but the SDK-specific entrypoint accepts the same
arguments.

```bash
lightning deployment create nginx-demo \
  --teamspace owner/teamspace \
  --image nginx:latest \
  --machine CPU \
  --port 80 \
  --replicas 1 \
  --api-key-auth
```

Inspect and stream logs:

```bash
lightning deployment inspect nginx-demo --teamspace owner/teamspace --jobs
lightning deployment logs nginx-demo --teamspace owner/teamspace --follow
```

Delete when finished:

```bash
lightning deployment delete nginx-demo --teamspace owner/teamspace --yes
```

# More examples

Runnable examples live in [`examples/`](examples/):

| Area                   | SDK tutorial                                | CLI tutorial                                        |
| ---------------------- | ------------------------------------------- | --------------------------------------------------- |
| studios                | [`studios.rst`](examples/studios.rst)       | [`studios_cli.rst`](examples/studios_cli.rst)       |
| jobs                   | [`jobs.rst`](examples/jobs.rst)             | [`jobs_cli.rst`](examples/jobs_cli.rst)             |
| multi-machine training | [`mmts.rst`](examples/mmts.rst)             | [`mmts_cli.rst`](examples/mmts_cli.rst)             |
| teamspaces             | [`teamspaces.rst`](examples/teamspaces.rst) | [`teamspaces_cli.rst`](examples/teamspaces_cli.rst) |
| sandboxes              | [`sandboxes.rst`](examples/sandboxes.rst)   | [`sandboxes_cli.rst`](examples/sandboxes_cli.rst)   |

# Development

From the repository root:

```bash
pip install -e ./python
```

From this directory:

```bash
pip install -e .
```

Build docs from the repository root:

```bash
uv run --group docs sphinx-build -M html python/docs/sdk python/docs/sdk/build -W --keep-going
uv run --group docs sphinx-build -M html python/docs/cli python/docs/cli/build -W --keep-going
```

# License

Apache-2.0. See [`../LICENSE`](../LICENSE).
