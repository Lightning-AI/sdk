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

## List jobs by tag

```go
jobs, err := teamspace.Jobs(lit.WithJobTags("prod", "nightly"))
if err != nil {
	log.Fatal(err)
}

for _, job := range jobs {
	fmt.Println(job.Name(), job.Tags())
}
```

Jobs carrying at least one of the tags are returned. `teamspace.MMTs(...)`
accepts the same option for multi-machine jobs, and `teamspace.Tags()` lists the tags
defined in the teamspace.

## Read a job's artifacts

Whatever a job writes to disk is kept in the teamspace drive, and stays there
until the job is deleted. The job handle reads it from anywhere:

```go
fmt.Println("Artifacts:", job.ArtifactsURI())

entries, err := job.ListArtifacts("", true)
if err != nil {
	log.Fatal(err)
}

for _, entry := range entries {
	fmt.Println(entry.Path, entry.Size)
}

if err := job.DownloadArtifacts("./artifacts", ""); err != nil {
	log.Fatal(err)
}
```

The first argument of `ListArtifacts` and the second of `DownloadArtifacts`
name a subfolder to work on, so a long training run does not have to come down
whole: `job.DownloadArtifacts("./checkpoints", "checkpoints")`.

`job.ArtifactsURI()` is the same location as a `lit://` address, which is what
`lightning ls` and `lightning cp` take and what the Lightning web UI shows under
the job. It is empty for a container job launched without an artifacts
destination, because such a job keeps nothing.

An MMT has no single artifact folder, because every machine writes its own.
`mmt.DownloadArtifacts` gives each machine a folder named after it, and
`mmt.ListArtifacts` prefixes each path the same way, so the listing and the
download agree.

A job's files sit directly under its name in the drive. A Studio in the same
teamspace mounts them one folder deeper, at `/teamspace/jobs/<job name>/artifacts`,
so a path copied out of a Studio does not address the drive.

# API shape

| Area                        | Entry point                                                                                |
| --------------------------- | ------------------------------------------------------------------------------------------ |
| users                       | `GetUser(...)`                                                                             |
| organizations               | `GetOrganization(...)`                                                                     |
| teamspaces                  | `GetTeamspace(...)`, `CreateTeamspace(...)`                                                |
| studios                     | `GetStudio(...)`, `CreateStudio(...)`, `studio.Start(...)`, `studio.SwitchMachine(...)`    |
| jobs                        | `GetJob(...)`, `RunJob(...)`, `job.Wait(...)`, `job.Stop(...)`, `job.Delete(...)`          |
| multi-machine training jobs | `GetMMT(...)`, `RunMMT(...)`                                                               |
| job artifacts               | `job.ArtifactsURI()`, `job.ListArtifacts(...)`, `job.DownloadArtifacts(...)`               |
| teamspace drive files       | `teamspace.ListFiles(...)`, `teamspace.DownloadFolder(...)`, `teamspace.DownloadFile(...)` |
| machines                    | `MachineCPU`, `MachineL4`, `MachineA100`, and other `Machine*` constants                   |

# Development

```bash
go test ./...
```

The Go module currently lives in [`go.mod`](go.mod) and targets Go 1.22.

### H200 and B200 machines

Use `MachineH200`, `MachineH200X2`, `MachineH200X4` and `MachineH200X8`, or
`MachineB200` and `MachineB200X8`, on every cloud.

# License

Apache-2.0. See [`../LICENSE`](../LICENSE).
