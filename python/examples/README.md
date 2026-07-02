<div align="center">

# Lightning SDK Examples

**Runnable Python and CLI examples for Lightning AI automation.**

______________________________________________________________________

<p align="center">
  <a href="#quick-start">Quick start</a> •
  <a href="#sdk-tutorials">SDK tutorials</a> •
  <a href="#cli-tutorials">CLI tutorials</a> •
  <a href="#running-examples">Running examples</a>
</p>

</div>

# Why these examples?

Each SDK tutorial has two parts:

- an executable `.py` file that can be run against a Lightning AI account
- a paired `.rst` guide that explains the workflow and keeps code snippets close
  to the runnable source

CLI tutorials use separate `*_cli.rst` files so shell workflows stay distinct
from Python automation.

Build on [Lightning AI](https://lightning.ai), the platform for training,
deploying, and scaling AI applications with managed compute, collaborative
studios, and production endpoints.

# Quick start

Install the SDK and authenticate:

```bash
pip install lightning-sdk
lightning login
```

Most examples need a Lightning AI teamspace. In docs and code snippets,
`owner/teamspace` means the owner and teamspace name visible in Lightning AI.
Replace placeholder names such as `sdk-tutorial-studio` with resources you can
create or access.

Sandbox examples can also use a sandbox-scoped API key:

```bash
export LIGHTNING_SANDBOX_API_KEY="..."
```

# SDK tutorials

| Tutorial                           | Runnable file                    | What it shows                                                                            |
| ---------------------------------- | -------------------------------- | ---------------------------------------------------------------------------------------- |
| [`studios.rst`](studios.rst)       | [`studios.py`](studios.py)       | Create, start, use, stop, and delete persistent studio workspaces                        |
| [`jobs.rst`](jobs.rst)             | [`jobs.py`](jobs.py)             | Submit container-backed and studio-backed jobs, wait for completion, inspect status      |
| [`mmts.rst`](mmts.rst)             | [`mmts.py`](mmts.py)             | Run and inspect multi-machine training jobs                                              |
| [`teamspaces.rst`](teamspaces.rst) | [`teamspaces.py`](teamspaces.py) | Resolve account context and inspect teamspace resources                                  |
| [`sandboxes.rst`](sandboxes.rst)   | [`sandboxes.py`](sandboxes.py)   | Create disposable or persistent sandboxes, run commands, write files, resume, and delete |

# CLI tutorials

| Tutorial                                   | What it shows                                                                       |
| ------------------------------------------ | ----------------------------------------------------------------------------------- |
| [`studios_cli.rst`](studios_cli.rst)       | Create, start, connect to, copy files into, and stop studios from the CLI           |
| [`jobs_cli.rst`](jobs_cli.rst)             | Submit, inspect, list, stop, and delete jobs from the CLI                           |
| [`mmts_cli.rst`](mmts_cli.rst)             | Launch and inspect multi-machine training runs from the CLI                         |
| [`teamspaces_cli.rst`](teamspaces_cli.rst) | Set CLI context and pass explicit teamspace scope to resource commands              |
| [`sandboxes_cli.rst`](sandboxes_cli.rst)   | Create sandboxes, run commands, inspect logs, stop, resume, and delete from the CLI |
| [`api_cli.rst`](api_cli.rst)               | Call authenticated Lightning API endpoints directly from shell scripts              |

# Running examples

Run SDK examples from this directory after authentication:

```bash
python sandboxes.py --teamspace owner/teamspace create
python jobs.py --teamspace my-teamspace --org my-org image
```

Run CLI examples from any directory:

```bash
lightning studio list --teamspace owner/teamspace
lightning deployment list --teamspace owner/teamspace
```

Use environment variables or CLI flags for secrets. Do not commit API keys,
tokens, private keys, or downloaded credentials into example files.
