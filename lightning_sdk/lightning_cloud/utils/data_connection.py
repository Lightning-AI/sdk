import os
from time import sleep, time
from lightning_sdk.lightning_cloud.openapi import Create, V1AwsDataConnection
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
import urllib3


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
        access_cluster_ids=[cluster_id],
        aws=V1AwsDataConnection(
            source=f"s3://{bucket_name}",
            region=region
    ))
    try:
        client.data_connection_service_create_data_connection(body, project_id)
    except (ApiException, urllib3.exceptions.HTTPError) as ex:
        # Note: This function can be called in a distributed way. 
        # There is a race condition where one machine might create the entry before another machine
        # and this request would fail with duplicated key
        # In this case, it is fine not to raise 
        if isinstance(ex, ApiException) and 'duplicate key value violates unique constraint' in str(ex.body):
            pass
        else:
            raise ex

    # Wait for the filesystem picks up the new data connection
    start = time()

    while not os.path.isdir(f"/teamspace/s3_connections/{bucket_name}") and (time() - start) < create_timeout:
        sleep(1)