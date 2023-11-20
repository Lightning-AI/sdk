import os
from time import sleep, time
from lightning_sdk.lightning_cloud.openapi import Create, V1AwsDataConnection

def add_s3_connection(bucket_name: str, region: str = "us-east-1", create_timeout: int = 15) -> None:
    """Utility to add a data connection."""
    from lightning_sdk.lightning_cloud import rest_client

    client = rest_client.LightningClient(retry=False)

    project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID")
    cluster_id = os.getenv("LIGHTNING_CLUSTER_ID")

    data_connections = client.data_connection_service_list_data_connections(project_id).data_connections

    if any(d for d in data_connections if d.name == bucket_name):
        return

    body = Create(
        name=bucket_name,
        create_index=True,
        cluster_id=cluster_id,
        aws=V1AwsDataConnection(
            source=f"s3://{bucket_name}",
            region=region
    ))
    client.data_connection_service_create_data_connection(body, project_id)

    # Wait for the filesystem picks up the new data connection
    start = time()

    while not os.path.isdir(f"/teamspace/s3_connections/{bucket_name}") and (time() - start) < create_timeout:
        sleep(1)