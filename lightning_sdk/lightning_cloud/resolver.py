import os
from typing import Optional, Union, Literal
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from abc import ABC, abstractmethod
from pathlib import Path
import sys
from time import sleep

# To avoid adding lightning_utilities as a dependency for now.
try:
    import boto3
    import botocore
    _BOTO3_AVAILABLE = True
except Exception:
    _BOTO3_AVAILABLE = False


try:
    from lightning_sdk import Studio, Machine
    _LIGHTNING_SDK_AVAILABLE = True
except:
    class Machine:
        pass
    _LIGHTNING_SDK_AVAILABLE = False

class _Resolver(ABC):
    @abstractmethod
    def __call__(self, root: str) -> Optional[str]:
        pass


class _LightningSrcResolver(_Resolver):
    """The `_LightningSrcResolver` enables to retrieve a cloud storage path from a directory."""

    def __call__(self, root: str) -> Optional[str]:
        if str(root).startswith("s3://"):
            return root

        root_absolute = str(Path(root).absolute())

        if root_absolute.startswith("/teamspace/studios/this_studio"):
            return None

        if root_absolute.startswith("/.project/cloudspaces") and len(root_absolute.split("/")) > 3:
            return self._resolve_studio(root_absolute, None, root_absolute.split("/")[3])

        if root_absolute.startswith("/teamspace/studios") and len(root_absolute.split("/")) > 3:
            return self._resolve_studio(root_absolute, root_absolute.split("/")[3], None)

        if root_absolute.startswith("/teamspace/s3_connections") and len(root_absolute.split("/")) > 3:
            return self._resolve_s3_connections(root_absolute)

        if root_absolute.startswith("/teamspace/datasets") and len(root_absolute.split("/")) > 3:
            return self._resolve_datasets(root_absolute)

        return None

    def _resolve_studio(self, root: str, target_name: str, target_id: str) -> str:
        client = LightningClient()

        # Get the ids from env variables
        cluster_id = os.getenv("LIGHTNING_CLUSTER_ID", None)
        project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID", None)

        if cluster_id is None:
            raise RuntimeError("The `cluster_id` couldn't be found from the environement variables.")

        if project_id is None:
            raise RuntimeError("The `project_id` couldn't be found from the environement variables.")

        clusters = client.cluster_service_list_clusters().clusters

        target_cloud_space = [
            cloudspace
            for cloudspace in client.cloud_space_service_list_cloud_spaces(
                project_id=project_id, cluster_id=cluster_id
            ).cloudspaces
            if cloudspace.name == target_name or cloudspace.id == target_id
        ]

        if not target_cloud_space:
            raise ValueError(f"We didn't find any matching Studio for the provided name `{target_name}`.")

        target_cluster = [cluster for cluster in clusters if cluster.id == target_cloud_space[0].cluster_id]

        if not target_cluster:
            raise ValueError(
                f"We didn't find a matching cluster associated with the id {target_cloud_space[0].cluster_id}."
            )

        bucket_name = target_cluster[0].spec.aws_v1.bucket_name

        return os.path.join(
            f"s3://{bucket_name}/projects/{project_id}/cloudspaces/{target_cloud_space[0].id}/code/content",
            *root.split("/")[4:],
        )

    def _resolve_s3_connections(self, root: str) -> str:
        client = LightningClient()

        # Get the ids from env variables
        project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID", None)
        if project_id is None:
            raise RuntimeError("The `project_id` couldn't be found from the environement variables.")

        target_name = root.split("/")[3]

        data_connections = client.data_connection_service_list_data_connections(project_id).data_connections

        data_connection = [dc for dc in data_connections if dc.name == target_name]

        if not data_connection:
            raise ValueError(f"We didn't find any matching data connection with the provided name `{target_name}`.")

        return os.path.join(data_connection[0].aws.source, *root.split("/")[4:])

    def _resolve_datasets(self, root: str) -> str:
        client = LightningClient()

        # Get the ids from env variables
        cluster_id = os.getenv("LIGHTNING_CLUSTER_ID", None)
        project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID", None)
        cloud_space_id = os.getenv("LIGHTNING_CLOUD_SPACE_ID", None)

        if cluster_id is None:
            raise RuntimeError("The `cluster_id` couldn't be found from the environement variables.")

        if project_id is None:
            raise RuntimeError("The `project_id` couldn't be found from the environement variables.")

        if cloud_space_id is None:
            raise RuntimeError("The `cloud_space_id` couldn't be found from the environement variables.")

        clusters = client.cluster_service_list_clusters().clusters

        target_cloud_space = [
            cloudspace
            for cloudspace in client.cloud_space_service_list_cloud_spaces(
                project_id=project_id, cluster_id=cluster_id
            ).cloudspaces
            if cloudspace.id == cloud_space_id
        ]

        if not target_cloud_space:
            raise ValueError(f"We didn't find any matching Studio for the provided id `{cloud_space_id}`.")

        target_cluster = [cluster for cluster in clusters if cluster.id == target_cloud_space[0].cluster_id]

        if not target_cluster:
            raise ValueError(
                f"We didn't find a matching cluster associated with the id {target_cloud_space[0].cluster_id}."
            )

        bucket_name = target_cluster[0].spec.aws_v1.bucket_name

        return os.path.join(
            f"s3://{bucket_name}/projects/{project_id}/datasets/",
            *root.split("/")[3:],
        )

class _LightningTargetResolver(_Resolver):
    """The `_LightningTargetResolver` generates a cloud storage path from a directory."""

    def __call__(self, name: str, version: Optional[int] = None) -> Optional[str]:
        # Get the ids from env variables
        cluster_id = os.getenv("LIGHTNING_CLUSTER_ID", None)
        project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID", None)

        if cluster_id is None or project_id is None:
            return

        if not _BOTO3_AVAILABLE:
            return

        client = LightningClient()

        clusters = client.cluster_service_list_clusters().clusters

        target_cluster = [cluster for cluster in clusters if cluster.id == cluster_id]

        if not target_cluster:
            raise ValueError(f"We didn't find a matching cluster associated with the id {cluster_id}.")

        prefix = os.path.join(f"projects/{project_id}/datasets/", name)

        s3 = boto3.client("s3")

        objects = s3.list_objects_v2(
            Bucket=target_cluster[0].spec.aws_v1.bucket_name,
            Delimiter="/",
            Prefix=prefix + "/",
        )
        if version is None:
            version = objects["KeyCount"] + 1 if objects["KeyCount"] else 0

        return os.path.join(f"s3://{target_cluster[0].spec.aws_v1.bucket_name}", prefix, f"version_{version}")

def _try_create_cache_dir(name: Optional[str], create: bool = False):
    # Get the ids from env variables
    cluster_id = os.getenv("LIGHTNING_CLUSTER_ID", None)
    project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID", None)

    if cluster_id is None or project_id is None and name is None:
        return

    cache_dir = os.path.join("/cache", name)
    
    if create:
        os.makedirs(cache_dir, exist_ok=True)

    return cache_dir


def _find_remote_dir(name: Optional[str], version: Optional[Union[int, Literal["latest"]]]) -> Optional[str]:
    # Get the ids from env variables
    cluster_id = os.getenv("LIGHTNING_CLUSTER_ID", None)
    project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID", None)

    if cluster_id is None or project_id is None or name is None:
        return None, False

    if not _BOTO3_AVAILABLE:
        return None, False

    client = LightningClient()

    clusters = client.cluster_service_list_clusters().clusters

    target_cluster = [cluster for cluster in clusters if cluster.id == cluster_id]

    if not target_cluster:
        raise ValueError(f"We didn't find a matching cluster associated with the id {cluster_id}.")

    prefix = os.path.join(f"projects/{project_id}/datasets/", name)

    s3 = boto3.client("s3")

    objects = s3.list_objects_v2(
        Bucket=target_cluster[0].spec.aws_v1.bucket_name,
        Delimiter="/",
        Prefix=prefix.strip("/") + "/",
    )

    contains_chunks = any(obj['Key'].endswith(".bin") for obj in objects['Contents'])

    if contains_chunks:
        cloud_storage_path = os.path.join(f"s3://{target_cluster[0].spec.aws_v1.bucket_name}", prefix)

        try:
            s3.head_object(Bucket=target_cluster[0].spec.aws_v1.bucket_name, Key=os.path.join(prefix, "index.json"))
            return cloud_storage_path, True
        except botocore.exceptions.ClientError:
            return cloud_storage_path, False

    latest_version = objects["KeyCount"] if objects["KeyCount"] else 0

    if version == "latest":
        version = latest_version
    elif version > latest_version:
        raise ValueError(f"The provided version doesn't exist. The `latest` version is {latest_version}.")

    cloud_storage_path = os.path.join(f"s3://{target_cluster[0].spec.aws_v1.bucket_name}", prefix, f"version_{version}")

    try:
        s3.head_object(Bucket=target_cluster[0].spec.aws_v1.bucket_name, Key=os.path.join(prefix, f"version_{version}", "index.json"))
        return cloud_storage_path, True
    except botocore.exceptions.ClientError:
        return cloud_storage_path, False

def get_lightning_sdk.lightning_cloud_url() -> str:
    # detect local development
    if os.getenv("VSCODE_PROXY_URI", "").startswith("http://localhost:9800"):
        return "http://localhost:9800"
    # DO NOT CHANGE!
    return os.getenv("LIGHTNING_CLOUD_URL", "https://lightning.ai")

def _execute(
    name: str,
    num_nodes: int,
    machine: Optional[Machine] = None,
    command: Optional[str] = None,
):
    """Remotely execute the current operator."""

    if not _LIGHTNING_SDK_AVAILABLE:
        raise ModuleNotFoundError("The `lightning_sdk` is required.")

    studio = Studio()
    job = studio._studio_api.create_data_prep_machine_job(
        command or f"cd {os.getcwd()} && python {sys.argv[0]}",
        name=name,
        num_instances=num_nodes,
        studio_id=studio._studio.id,
        teamspace_id=studio._teamspace.id,
        cluster_id=studio._studio.cluster_id,
        cloud_compute=machine or studio._studio_api.get_machine(studio._studio.id, studio._teamspace.id),
    )

    has_printed = False

    while True:
        curr_job = studio._studio_api._client.lightningapp_instance_service_get_lightningapp_instance(
            project_id=studio._teamspace.id, id=job.id
        )
        if not has_printed:
            cloud_url = get_lightning_sdk.lightning_cloud_url()
            job_url = f"{cloud_url}/{studio._user.username}/{studio._teamspace.name}"
            job_url += f"/studios/{studio.name}/app?app_id=data-prep&job_name={curr_job.name}"
            print(f"Find your job at {job_url}")
            has_printed = True

        if curr_job.status.phase == "LIGHTNINGAPP_INSTANCE_STATE_FAILED":
            raise RuntimeError(f"job {curr_job.name} failed!")

        if curr_job.status.phase == "LIGHTNINGAPP_INSTANCE_STATE_STOPPED":
            break

        sleep(1)