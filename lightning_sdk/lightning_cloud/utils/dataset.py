from typing import Optional, List, Tuple, Union
import os
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.lightning_cloud.openapi import (
    ProjectIdDatasetsBody,
    V1DatasetType,
)

def _create_dataset(
    input_dir: str,
    storage_dir: str,
    dataset_type: V1DatasetType,
    empty: Optional[bool] = None,
    size: Optional[int] = None,
    num_bytes: Optional[int] = None,
    data_format: Optional[Union[str, Tuple[str]]] = None,
    compression: Optional[str] = None,
    num_chunks: Optional[str] = None,
    num_bytes_per_chunk: Optional[List[int]] = None,
    name: Optional[str] = None,
    version: Optional[int] = None,
):
    """
    Create a dataset with metadata information about its source and destination
    """
    project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID", None)
    cluster_id = os.getenv("LIGHTNING_CLUSTER_ID", None)
    user_id = os.getenv("LIGHTNING_USER_ID", None)
    cloud_space_id = os.getenv("LIGHTNING_CLOUD_SPACE_ID", None)
    lightning_app_id = os.getenv("LIGHTNING_CLOUD_APP_ID", None)

    if project_id is None:
        return

    if not storage_dir:
        raise ValueError("The storage_dir should be defined.")

    client = LightningClient(retry=False)

    client.dataset_service_create_dataset(
        body=ProjectIdDatasetsBody(
            cloud_space_id=cloud_space_id if lightning_app_id is None else None,
            cluster_id=cluster_id,
            creator_id=user_id,
            empty=empty,
            input_dir=input_dir,
            lightning_app_id=lightning_app_id,
            name=name,
            size=size,
            num_bytes=num_bytes,
            data_format=str(data_format) if data_format else data_format,
            compression=compression,
            num_chunks=num_chunks,
            num_bytes_per_chunk=num_bytes_per_chunk,
            storage_dir=storage_dir,
            type=dataset_type,
            version=version,
        ),
        project_id=project_id
    )