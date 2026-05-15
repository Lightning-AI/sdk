"""Create, inspect, update, log, and delete a Lightning deployment.

Set LIGHTNING_TEAMSPACE to "owner/teamspace" before running this example.
Set DELETE_DEPLOYMENT=1 to delete the deployment at the end.
"""

import os

from lightning_sdk import Machine
from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.deployment import ApiKeyAuth, Deployment

teamspace = os.environ["LIGHTNING_TEAMSPACE"]
name = os.environ.get("LIGHTNING_DEPLOYMENT_NAME", "nginx-sdk-example")
replicas = int(os.environ.get("LIGHTNING_DEPLOYMENT_REPLICAS", "1"))

deployment = Deployment(name=name, teamspace=teamspace)
if not deployment.is_started:
    deployment.start(
        image="nginx:latest",
        machine=Machine.CPU,
        ports=[80],
        replicas=replicas,
        auth=ApiKeyAuth(),
    )
    print(f"Created deployment {deployment.name}")

deployment.update(replicas=replicas)
print(f"Updated deployment {deployment.name} to {replicas} replicas")

api = DeploymentApi()
deployment_record = api.get_deployment_by_name(deployment.name, deployment.teamspace.id)
print(deployment_record.to_dict())

jobs = api.list_deployment_jobs(deployment.teamspace.id, deployment_record.id)
for job in jobs:
    logs = api.get_job_logs(deployment.teamspace.id, job.id, deployment_id=deployment_record.id)
    print(f"{job.id}: {len(logs.pages or [])} log pages")

if os.environ.get("DELETE_DEPLOYMENT") == "1":
    api.delete_deployment(deployment_record)
    print(f"Deleted deployment {deployment.name}")
