<div align="center">

# Lightning SDK for Go

**Automate Lightning AI resources from Go services, CLIs, and CI jobs.**

______________________________________________________________________

<p align="center">
  <a href="#quick-start">Quick start</a> •
  <a href="#examples">Examples</a> •
  <a href="#api-shape">API shape</a> •
  <a href="#development">Development</a>
</p>

[![Go](https://img.shields.io/badge/go-%3E%3D1.22-blue.svg)](go.mod)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](../LICENSE)

</div>

# Why Lightning SDK for Go?

The Go SDK exposes Lightning AI resources as typed handles. Use it when Go code
needs to resolve users, organizations, or teamspaces, then create or manage
studios, single-machine jobs, and multi-machine training jobs.

The public package is `lit`. Handles are created with `Get*`, `Create*`, and
`Run*` functions and then operated through methods on the returned resource.

Build on [Lightning AI](https://lightning.ai), the platform for training,
deploying, and scaling AI applications with managed compute, collaborative
studios, and production endpoints.

# Quick start

Add the module:

```bash
go get github.com/lightning-ai/sdk/go
```

Authenticate with the same environment used by other Lightning SDKs:

```bash
export LIGHTNING_USER_ID="..."
export LIGHTNING_API_KEY="..."
```

Run a container-backed job:

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

# Examples

## Resolve a teamspace

```go
org, err := lit.GetOrganization("my-org")
if err != nil {
	log.Fatal(err)
}

teamspace, err := lit.GetTeamspace("my-teamspace", lit.TeamspaceOptions{Owner: org})
if err != nil {
	log.Fatal(err)
}

fmt.Println(teamspace.ID())
```

## Create and start a Studio

```go
studio, err := lit.CreateStudio("go-dev", lit.StudioOptions{
	Teamspace: teamspace,
	Machine:   lit.MachineCPU,
})
if err != nil {
	log.Fatal(err)
}

if err := studio.Start(); err != nil {
	log.Fatal(err)
}

fmt.Println(studio.Status())
```

## Fetch an existing job

```go
job, err := lit.GetJob("go-readme-job", lit.JobOptions{Teamspace: teamspace})
if err != nil {
	log.Fatal(err)
}

fmt.Println(job.Name(), job.Status(), job.Machine())
```

# API shape

| Area                        | Entry point                                                                             |
| --------------------------- | --------------------------------------------------------------------------------------- |
| users                       | `GetUser(...)`                                                                          |
| organizations               | `GetOrganization(...)`                                                                  |
| teamspaces                  | `GetTeamspace(...)`, `CreateTeamspace(...)`                                             |
| studios                     | `GetStudio(...)`, `CreateStudio(...)`, `studio.Start(...)`, `studio.SwitchMachine(...)` |
| jobs                        | `GetJob(...)`, `RunJob(...)`, `job.Wait(...)`, `job.Stop(...)`, `job.Delete(...)`       |
| multi-machine training jobs | `GetMMT(...)`, `RunMMT(...)`                                                            |
| machines                    | `MachineCPU`, `MachineL4`, `MachineA100`, and other `Machine*` constants                |

# Development

```bash
go test ./...
```

The Go module currently lives in [`go.mod`](go.mod) and targets Go 1.22.

# License

Apache-2.0. See [`../LICENSE`](../LICENSE).
