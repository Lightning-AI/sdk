import contextlib
import os
from typing import Optional

import requests
import urllib3

from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.lightning_cloud.openapi import V1Membership, V1ProjectClusterBinding
from lightning_sdk.lightning_cloud.rest_client import LightningClient

_CHUNK_SIZE = 1024 * 1024


def _get_project(client: LightningClient, project_name: Optional[str] = None) -> V1Membership:
    """Get a project membership for the user from the backend."""
    projects = client.projects_service_list_memberships()
    if len(projects.memberships) == 0:
        raise ValueError("No valid projects found. Please reach out to lightning.ai team to create a project")

    if project_name is None:
        return projects.memberships[0]

    matches = []
    for membership in projects.memberships:
        if membership.name == project_name or membership.display_name == project_name:
            matches.append(membership)

    if len(matches) == 1:
        return matches[0]

    if len(matches) >= 2:
        raise ValueError(f"We found several teamspaces. Which one do you want to use {[m.name for m in matches]}")

    raise ValueError("No valid projects found. Please reach out to lightning.ai team to create a project")


def _get_cluster(
    client: LightningClient, project_id: str, cluster_id: Optional[str] = None, allow_neoclouds: bool = False
) -> V1ProjectClusterBinding:
    """Get a project membership for the user from the backend."""
    clusters = client.projects_service_list_project_cluster_bindings(project_id=project_id)
    if cluster_id:
        for cluster in clusters.clusters:
            if cluster.cluster_id == cluster_id:
                return cluster
        raise ValueError(
            f"No valid cluster found with the provided {cluster_id}."
            f"Found {[c.cluster_id for c in clusters.clusters]}."
        )

    # filter neoclouds out
    if not allow_neoclouds:
        cluster_objs = client.cluster_service_list_clusters(project_id=project_id)
        # filter for aws or gcp cluster
        valid_clusters = filter(
            lambda c: c.spec.aws_v1 is not None or c.spec.google_cloud_v1 is not None, cluster_objs.clusters
        )
        valid_clusters = {c.id for c in valid_clusters}

        if len(valid_clusters):
            clusters.clusters = list(filter(lambda c: c.cluster_id in valid_clusters, clusters.clusters))

    clusters = sorted(clusters.clusters, key=lambda x: x.created_at)
    if len(clusters):
        return clusters[0]
    return None


def _get_service_url(cloud_space_id: str, file_endpoint_id: str) -> str:
    url = _get_cloud_url()
    domain = _get_domain(url)
    protocol = _get_protocol(url)
    return f"{protocol}//{file_endpoint_id}-{cloud_space_id}.cloudspaces.{domain}"


def _get_domain(url: str) -> str:
    base_url = url.split("//")[1].split("/")[0]
    if "localhost:9800" in base_url:
        return "local.litng.ai:8118"
    if "lightning.ai" in base_url and "localhost:8888" in base_url:
        return "litng.ai"
    return base_url


def _get_protocol(url: str) -> str:
    return url.split("//")[0]


def download_file(filepath: str, cache_dir: str = "/cache") -> str:
    """Download the file passed to the service execution by the user."""
    service_id = os.getenv("LIGHTNING_SERVICE_EXECUTION_ID")

    if service_id is None:
        raise RuntimeError("The ServiceId is required. Please reach out to lightning.ai team.")

    # Note: Make the function idempotent
    prefix = os.path.join(cache_dir, service_id)
    if not filepath.startswith(prefix):
        saved_filepath = filepath
        if saved_filepath.startswith("/"):
            saved_filepath = saved_filepath[1:]
        saved_filepath = os.path.join(prefix, saved_filepath)
    else:
        saved_filepath = filepath
        filepath = filepath.replace(prefix, "")

    if os.path.exists(saved_filepath):
        return saved_filepath

    client = LightningClient(retry=False)
    download_artifacts = client.endpoint_service_download_service_execution_artifact(
        project_id=os.getenv("LIGHTNING_CLOUD_PROJECT_ID"), id=service_id, page_token=None, filepath=filepath
    )
    artifact = download_artifacts.artifacts[0]

    os.makedirs(os.path.dirname(saved_filepath), exist_ok=True)

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    with contextlib.suppress(ConnectionError):
        request = requests.get(artifact.url, stream=True, verify=False)
        with open(saved_filepath, "wb") as fp:
            for chunk in request.iter_content(chunk_size=_CHUNK_SIZE):
                fp.write(chunk)  # type: ignore
    return saved_filepath
