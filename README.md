<div align="center">

# Lightning SDK

**Build, automate, and deploy on Lightning AI from Python, TypeScript, and Go.**

______________________________________________________________________

<p align="center">
  <a href="#quick-start">Quick start</a> •
  <a href="#packages">Packages</a> •
  <a href="#development">Development</a> •
  <a href="https://lightning.ai/docs/overview/sdk-reference">Docs</a>
</p>

[![PyPI](https://img.shields.io/pypi/v/lightning-sdk.svg)](https://pypi.org/project/lightning-sdk/)
[![npm](https://img.shields.io/npm/v/@lightningai/sdk.svg)](https://www.npmjs.com/package/@lightningai/sdk)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

</div>

# Why Lightning SDK?

Lightning SDK is the programmatic interface for Lightning AI resources. Use it
when scripts, notebooks, services, or CI jobs need to create compute, run work,
inspect state, stream logs, move files, or clean up resources without clicking
through the UI.

The repo contains the Python SDK and CLI, a TypeScript SDK, and a Go SDK. The
Python package covers platform automation across studios, jobs, deployments,
teamspaces, and sandboxes. The TypeScript package focuses on sandboxes: create
isolated environments, run commands, use PTY sessions, and read or write files.
The Go package exposes Lightning resources as typed handles for users,
organizations, teamspaces, studios, jobs, and multi-machine training jobs.

Build on [Lightning AI](https://lightning.ai), the platform for training,
deploying, and scaling AI applications with managed compute, collaborative
studios, and production endpoints.

# Quick start

Install the interface you need:

```bash
pip install lightning-sdk
npm install @lightningai/sdk
go get github.com/lightning-ai/sdk/go
```

Authenticate once for the Python SDK, Go SDK, and CLI:

```bash
lightning login
```

For TypeScript sandboxes, export an API key from Lightning AI account settings:

```bash
export LIGHTNING_API_KEY="..."
```

Start with the workflow you need. Each workflow below shows the same task across
the SDKs and CLI wherever that surface is available.

## Studio

Use a Studio for a persistent cloud development environment. Available in
Python, Go, and the CLI.

### Python

```python
from lightning_sdk import Machine, Studio

studio = Studio("readme-studio", teamspace="owner/teamspace", create_ok=True)
studio.start(Machine.CPU)
print(studio.run("python --version"))
studio.stop()
```

### Go

```go
package main

import (
	"fmt"
	"log"

	lit "github.com/lightning-ai/sdk/go"
)

func main() {
	org, err := lit.GetOrganization("my-org")
	if err != nil {
		log.Fatal(err)
	}

	teamspace, err := lit.GetTeamspace("my-teamspace", lit.TeamspaceOptions{Owner: org})
	if err != nil {
		log.Fatal(err)
	}

	studio, err := lit.CreateStudio("readme-studio", lit.StudioOptions{
		Teamspace: teamspace,
		Machine:   lit.MachineCPU,
	})
	if err != nil {
		log.Fatal(err)
	}

	if err := studio.Start(); err != nil {
		log.Fatal(err)
	}

	output, err := studio.Run("python --version")
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println(output)
}
```

### CLI

```bash
lightning studio start \
  --name readme-studio \
  --teamspace owner/teamspace \
  --machine CPU \
  --create
```

## Job

Use a job for container-backed batch work. Available in Python, Go, and the CLI.

### Python

```python
from lightning_sdk import Job, Machine

job = Job.run(
    name="readme-job",
    image="python:3.11-slim",
    machine=Machine.CPU,
    teamspace="owner/teamspace",
    command="python -c 'print(\"hello from Lightning\")'",
)

job.wait()
print(job.status)
```

### Go

```go
package main

import (
	"fmt"
	"log"

	lit "github.com/lightning-ai/sdk/go"
)

func main() {
	org, err := lit.GetOrganization("my-org")
	if err != nil {
		log.Fatal(err)
	}

	teamspace, err := lit.GetTeamspace("my-teamspace", lit.TeamspaceOptions{Owner: org})
	if err != nil {
		log.Fatal(err)
	}

	job, err := lit.RunJob(
		"go-readme-job",
		lit.MachineCPU,
		"python -c 'print(\"hello from Lightning\")'",
		lit.JobOptions{
			Teamspace: teamspace,
			Image:     "python:3.11-slim",
		},
	)
	if err != nil {
		log.Fatal(err)
	}

	if err := job.Wait(); err != nil {
		log.Fatal(err)
	}
	fmt.Println(job.Status())
}
```

### CLI

```bash
lightning job run \
  --name readme-job \
  --teamspace owner/teamspace \
  --image python:3.11-slim \
  --machine CPU \
  --command "python -c 'print(\"hello from Lightning\")'"
```

## Sandbox

Use a sandbox for disposable or persistent command execution with file and PTY
support. Available in Python, TypeScript, and the CLI.

### Python

```python
from lightning_sdk.sandbox import Sandbox

sandbox = Sandbox.create(name="readme-sandbox", instance_type="cpu-1")
command = sandbox.run_command("python --version")
print(command.output)
sandbox.delete()
```

### TypeScript

```ts
import { Sandbox } from "@lightningai/sdk";

const sandbox = await Sandbox.create({
  name: "readme-sandbox",
  instanceType: "cpu-1",
});

const result = await sandbox.runCommand("echo", ["hello from Lightning"]);
console.log(result.output);

await sandbox.delete();
```

### CLI

```bash
lightning sandbox create \
  --name readme-sandbox \
  --teamspace owner/teamspace \
  --instance-type cpu-1 \
  --json

export SANDBOX_ID=sbx_1234567890
lightning sandbox run "$SANDBOX_ID" -- python -c "print('hello from Lightning')"
lightning sandbox delete "$SANDBOX_ID"
```

# Packages

| Package            | Path                 | Install                                 | Use it for                                                                                         |
| ------------------ | -------------------- | --------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Python SDK and CLI | [`python/`](python/) | `pip install lightning-sdk`             | studios, jobs, deployments, teamspaces, sandboxes, and CLI automation                              |
| TypeScript SDK     | [`js/`](js/)         | `npm install @lightningai/sdk`          | Sandbox creation, commands, files, PTY sessions, and snapshots                                     |
| Go SDK             | [`go/`](go/)         | `go get github.com/lightning-ai/sdk/go` | Typed handles for users, organizations, teamspaces, studios, jobs, and multi-machine training jobs |

# Authentication

For the Python SDK and CLI, run `lightning login` or export
`LIGHTNING_USER_ID` and `LIGHTNING_API_KEY` from Lightning AI account settings.
Inside a Lightning Studio, these values are usually already available.

Sandbox-only API keys can also be passed through `LIGHTNING_SANDBOX_API_KEY` or
configured directly in code with `Sandbox.configure(...)`.

# Development

This repository is a monorepo. To work on the Python package from the repo root:

```bash
pip install -e ./python
```

To work on the TypeScript package:

```bash
cd js
npm install
npm run build
```

To work on the Go package:

```bash
cd go
go test ./...
```

Run package-specific tests from the relevant package directory. See
[`python/README.md`](python/README.md), [`js/README.md`](js/README.md),
[`go/README.md`](go/README.md), and [`python/examples/README.md`](python/examples/README.md)
for narrower package guides.

# Community

Read the [SDK docs](https://lightning.ai/docs/overview/sdk-reference), build on
[Lightning AI](https://lightning.ai), and use the Apache-2.0 license terms in
[`LICENSE`](LICENSE).
