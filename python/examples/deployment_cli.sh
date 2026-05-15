#!/usr/bin/env bash
set -euo pipefail

# Set LIGHTNING_TEAMSPACE to "owner/teamspace".
# Set LIGHTNING_CLI to override the command, for example:
#   LIGHTNING_CLI="uvx --with-editable=. lightning-sdk"

TEAMSPACE="${LIGHTNING_TEAMSPACE:?Set LIGHTNING_TEAMSPACE to owner/teamspace}"
NAME="${LIGHTNING_DEPLOYMENT_NAME:-nginx-cli-example}"
UPDATED_NAME="${LIGHTNING_DEPLOYMENT_UPDATED_NAME:-${NAME}-updated}"
CLOUD_ACCOUNT="${LIGHTNING_CLOUD_ACCOUNT:-}"

if [[ -n "${LIGHTNING_CLI:-}" ]]; then
  read -r -a CLI <<< "${LIGHTNING_CLI}"
else
  CLI=(uvx lightning-sdk)
fi

CREATE_ARGS=(
  deployment create "${NAME}"
  --teamspace "${TEAMSPACE}"
  --image nginx:latest
  --machine CPU
  --port 80
  --replicas 1
  --api-key-auth
)
if [[ -n "${CLOUD_ACCOUNT}" ]]; then
  CREATE_ARGS+=(--cloud-account "${CLOUD_ACCOUNT}")
fi

"${CLI[@]}" "${CREATE_ARGS[@]}"
"${CLI[@]}" deployment list --teamspace "${TEAMSPACE}"
"${CLI[@]}" deployment inspect "${NAME}" --teamspace "${TEAMSPACE}" --jobs

JOB_ID="$("${CLI[@]}" deployment inspect "${NAME}" --teamspace "${TEAMSPACE}" --jobs | python -c 'import json,sys; jobs=json.load(sys.stdin).get("jobs") or []; print(jobs[0]["id"] if jobs else "")')"
"${CLI[@]}" deployment logs "${NAME}" --teamspace "${TEAMSPACE}"
if [[ -n "${JOB_ID}" ]]; then
  "${CLI[@]}" deployment logs "${NAME}" --teamspace "${TEAMSPACE}" --job-id "${JOB_ID}"
fi

"${CLI[@]}" deployment update "${NAME}" --teamspace "${TEAMSPACE}" --new-name "${UPDATED_NAME}" --replicas 0
"${CLI[@]}" deployment delete "${UPDATED_NAME}" --teamspace "${TEAMSPACE}" --yes
