import os
from typing import Optional

from lightning_sdk.lightning_cloud.openapi import V1Membership
from lightning_sdk.lightning_cloud.rest_client import LightningClient

LIGHTNING_CLOUD_PROJECT_ID = os.getenv("LIGHTNING_CLOUD_PROJECT_ID")


def _get_project(client: LightningClient, project_id: Optional[str] = None, verbose: bool = True) -> V1Membership:
    """Get a project membership for the user from the backend."""
    if project_id is None:
        project_id = LIGHTNING_CLOUD_PROJECT_ID

    if project_id is not None:
        project = client.projects_service_get_project(project_id)
        if not project:
            raise ValueError(
                "Environment variable `LIGHTNING_CLOUD_PROJECT_ID` is set but could not find an associated project."
            )
        return V1Membership(
            name=project.name,
            display_name=project.display_name,
            description=project.description,
            created_at=project.created_at,
            project_id=project.id,
            owner_id=project.owner_id,
            owner_type=project.owner_type,
            quotas=project.quotas,
            updated_at=project.updated_at,
        )

    projects = client.projects_service_list_memberships()
    if len(projects.memberships) == 0:
        raise ValueError("No valid projects found. Please reach out to lightning.ai team to create a project")
    if len(projects.memberships) > 1 and verbose:
        print(f"Defaulting to the project: {projects.memberships[0].name}")
    return projects.memberships[0]
