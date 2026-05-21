#!/usr/bin/env bash
set -euo pipefail

# Raw Lightning API examples.
#
# Prerequisites:
#   lightning login
#   jq
#
# When running from this repository instead of an installed CLI:
#   LIGHTNING="uv run python -m lightning_sdk.cli.entrypoint" bash examples/api.sh

LIGHTNING=${LIGHTNING:-lightning-sdk}

# List projects/teamspaces the current user can access.
$LIGHTNING api /v1/memberships

# List project/teamspace names only.
$LIGHTNING api /v1/memberships | jq -r '.memberships[].name'

# List project/teamspace IDs and names.
$LIGHTNING api /v1/memberships | jq -r '.memberships[] | [.projectId, .name] | @tsv'

# Use PROJECT_ID to pick a specific teamspace. Defaults to the first one.
PROJECT_ID=${PROJECT_ID:-$($LIGHTNING api /v1/memberships | jq -r '.memberships[0].projectId')}

# List deployments in a project/teamspace.
$LIGHTNING api "/v1/projects/${PROJECT_ID}/deployments" -X GET -F limit=20

# List deployment names only.
$LIGHTNING api "/v1/projects/${PROJECT_ID}/deployments" -X GET -F limit=20 | jq -r '.deployments[].name'

# List jobs in a project/teamspace.
$LIGHTNING api "/v1/projects/${PROJECT_ID}/jobs" -X GET -F limit=20

# List job names only.
$LIGHTNING api "/v1/projects/${PROJECT_ID}/jobs" -X GET -F limit=20 | jq -r '.jobs[].name'

# Sandboxes require an organization ID unless your API key is already org-scoped.
# Defaults to the first organization-owned project/teamspace owner.
ORG_ID=${ORG_ID:-$($LIGHTNING api /v1/memberships | jq -r '[.memberships[] | select(.ownerType == "organization") | .ownerId][0] // empty')}

if [[ -n "${ORG_ID}" ]]; then
  # List sandboxes in an organization. Add projectId to scope to one teamspace.
  $LIGHTNING api /v1/core/sandboxes -X GET -f "organizationId=${ORG_ID}" -f "projectId=${PROJECT_ID}" -f limit=20

  # List sandbox names only. Some older sandboxes may only have an ID.
  $LIGHTNING api /v1/core/sandboxes -X GET -f "organizationId=${ORG_ID}" -f "projectId=${PROJECT_ID}" -f limit=20 \
    | jq -r '.sandboxes[] | .name // .id'
else
  echo "Skipping sandbox examples: set ORG_ID=<organization-id> or use an org-scoped API key." >&2
fi
