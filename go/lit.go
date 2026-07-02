// Package lit is the official Go SDK for Lightning AI.
//
// The SDK exposes Lightning resources — users, organizations, teamspaces,
// studios, jobs, and multi-machine jobs (MMTs) — as plain Go types with
// unexported state, mirroring the Python SDK's flat lightning_sdk namespace.
// Handles are obtained through the Get*, Create*, and Run* functions and
// navigated through methods on the returned resources.
package lit
