import os
from time import sleep, time
from lightning_sdk.lightning_cloud import rest_client
from lightning_sdk.lightning_cloud.openapi import Create, V1AwsDataConnection, V1S3FolderDataConnection, V1EfsConfig, V1GcpDataConnection, V1FilestoreDataConnection, V1DataConnectionTier, V1R2DataConnection
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
import urllib3

def add_s3_connection(bucket_name: str, region: str = "us-east-1", create_timeout: int = 15) -> None:
    """Utility to add a data connection."""
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

    return

def create_s3_folder(folder_name: str, create_timeout: int = 15) -> None:
    """
    Utility function to create a writable S3 folder.

    Parameters:
        1. folder_name (str): The name of the folder to create.
        2. create_timeout (int): The timeout for the folder creation.
    Returns:
        None
    """
    client = rest_client.LightningClient(retry=False)

    project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID")
    cluster_id = os.getenv("LIGHTNING_CLUSTER_ID")

    # Get existing data connections
    data_connections = client.data_connection_service_list_data_connections(project_id).data_connections

    for connection in data_connections:
        existing_folder_name = getattr(connection, 'name', None)
        isS3Folder = getattr(connection, 's3_folder', None) is not None

        if existing_folder_name == folder_name and isS3Folder:
            return

    # If we get here, no matching folder was found, proceed with creation
    body = Create(
        name=folder_name,
        create_resources=True,
        cluster_id=cluster_id,
        access_cluster_ids=[cluster_id],
        force=True,
        writable=True,
        s3_folder=V1S3FolderDataConnection()
    )
    try:
        client.data_connection_service_create_data_connection(body, project_id)
    except (ApiException, urllib3.exceptions.HTTPError) as ex:
        # Note: This function can be called in a distributed way.
        # There is a race condition where one machine might create the entry before another machine
        # and this request would fail with duplicated key
        # In this case, it is fine not to raise
        if isinstance(ex, ApiException) and 'duplicate key value violates unique constraint' in str(ex.body):
            pass
        else:
            raise ex

    # Wait for the filesystem picks up the new data connection
    start = time()

    while not os.path.isdir(f"/teamspace/s3_folders/{folder_name}") and (time() - start) < create_timeout:
        sleep(1)

    return

def create_efs_folder(folder_name: str, region: str, create_timeout: int = 60) -> None:
    """
    Utility function to create a EFS folder.

    Args:
        folder_name: The name of the folder to create.
        region: the region to create the efs in. Could be something like "us-east-1"
        create_timeout: Timeout for creating the efs folder. Defaults to 60 seconds
    """
    client = rest_client.LightningClient(retry=False)

    project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID")
    cluster_id = os.getenv("LIGHTNING_CLUSTER_ID")


    # Get existing data connections
    data_connections = client.data_connection_service_list_data_connections(project_id).data_connections

    for connection in data_connections:
        existing_folder_name = getattr(connection, 'name', None)
        isEFS = getattr(connection, 'efs', None) is not None

        if existing_folder_name == folder_name and isEFS:
            return

    # If we get here, no matching folder was found, proceed with creation
    body = Create(
        name=folder_name,
        create_resources=True,
        cluster_id=cluster_id,
        access_cluster_ids=[cluster_id],
        force=True,
        writable=True,
        efs=V1EfsConfig(region=region),
    )
    try:
        connection = client.data_connection_service_create_data_connection(body, project_id)
    except ApiException as e:
        # Note: This function can be called in a distributed way.
        # There is a race condition where one machine might create the entry before another machine
        # and this request would fail with duplicated key
        # In this case, it is fine not to raise
        if'duplicate key value violates unique constraint' in str(e.body):
            return
        raise e from None

    except urllib3.exceptions.HTTPError as e:
        raise e from None

    start = time()
    while True:
        if time() - start > create_timeout:
            print(f"Dataconnection {connection.name} didn't become accessible withing {create_timeout} seconds!")


        data_connection = client.data_connection_service_get_data_connection(project_id=project_id, id=connection.id)
        if data_connection.accessible:
            break

        sleep(1)

def add_efs_connection(name: str, filesystem_id: str, region: str = "us-east-1", create_timeout: int = 60) -> None:
    """Utility to add an existing EFS filesystem as a data connection.

    Args:
        name: The name to give to the data connection
        filesystem_id: The ID of the existing EFS filesystem (e.g., 'fs-1234567')
        region: AWS region where the EFS filesystem exists (default: 'us-east-1')
        create_timeout: Timeout in seconds to wait for the connection to be accessible (default: 60)
    """
    client = rest_client.LightningClient(retry=False)

    project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID")
    cluster_id = os.getenv("LIGHTNING_CLUSTER_ID")

    data_connections = client.data_connection_service_list_data_connections(project_id).data_connections

    if any(d for d in data_connections if d.name == name):
        return

    body = Create(
        name=name,
        create_resources=False,  # Don't create new EFS since we're connecting to existing one
        cluster_id=cluster_id,
        access_cluster_ids=[cluster_id],
        force=True,
        writable=True,
        efs=V1EfsConfig(
            region=region,
            file_system_id=filesystem_id,
        )
    )

    try:
        connection = client.data_connection_service_create_data_connection(body, project_id)
    except (ApiException, urllib3.exceptions.HTTPError) as ex:
        if isinstance(ex, ApiException) and 'duplicate key value violates unique constraint' in str(ex.body):
            pass
        else:
            raise ex

    start = time()
    while True:
        if time() - start > create_timeout:
            print(f"Dataconnection {connection.name} didn't become accessible withing {create_timeout} seconds!")
            break

        data_connection = client.data_connection_service_get_data_connection(project_id=project_id, id=connection.id)
        if data_connection.accessible:
            break

        sleep(1)

    return

def add_gcs_connection(connection_name: str, bucket_name: str, create_timeout: int = 15) -> None:
    """
    Utility function to add a GCS data connection.

    Parameters:
        1. connection_name (str): The name of the data connection.
        2. bucket_name (str): The name of the bucket to attach.
        3. create_timeout (int): The timeout for the data connectio creation.
    Returns:
        None
    """

    client = rest_client.LightningClient(retry=False)

    project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID")
    cluster_id = os.getenv("LIGHTNING_CLUSTER_ID")

    # Get existing data connections and ensure there is no an existing one with the same name and type
    data_connections = client.data_connection_service_list_data_connections(project_id).data_connections

    for connection in data_connections:
        existing_connection_name = getattr(connection, 'name', None)
        isGCSConnection = getattr(connection, 'gcp', None) is not None

        # Same name and type already exists
        if existing_connection_name == connection_name and isGCSConnection:
            return

    body = Create(
        name=connection_name,
        create_index=True,
        cluster_id=cluster_id,
        access_cluster_ids=[cluster_id],
        gcp=V1GcpDataConnection(
            source=f"gs://{bucket_name}",
        ))
    try:
        client.data_connection_service_create_data_connection(body, project_id)
    except (ApiException, urllib3.exceptions.HTTPError) as ex:
        # Note: This function can be called in a distributed way.
        # There is a race condition where one machine might create the entry before another machine
        # and this request would fail with duplicated key
        # In this case, it is fine not to raise
        if isinstance(ex, ApiException) and 'duplicate key value violates unique constraint' in str(ex.body):
            pass
        else:
            raise ex

    # Wait for the filesystem picks up the newly added GCS data connection
    start = time()

    while not os.path.isdir(f"/teamspace/gcs_connections/{bucket_name}") and (time() - start) < create_timeout:
        sleep(1)

    return

def create_filestore_folder(folder_name: str, region: str, capacity_gb: int = 1024, tier: V1DataConnectionTier = V1DataConnectionTier.HDD, create_timeout: int = 600) -> None:
    """
    Utility function to create a Filestore folder.

    Args:
        folder_name: The name of the folder to create.
        region: the region to create the folder in, e.g. "us-central1".
        capacity_gb: capacity of the Filestore folder.
        tier: Filestore folder tier, SSD or HDD.
        create_timeout (int): The timeout for the folder creation.
    """
    client = rest_client.LightningClient(retry=False)

    project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID")
    cluster_id = os.getenv("LIGHTNING_CLUSTER_ID")

    # Get existing data connections
    data_connections = client.data_connection_service_list_data_connections(project_id).data_connections

    for connection in data_connections:
        existing_folder_name = getattr(connection, 'name', None)
        isFilestore = getattr(connection, 'filestore', None) is not None

        if existing_folder_name == folder_name and isFilestore:
            return

    # If we get here, no matching folder was found, proceed with creation
    body = Create(
        name=folder_name,
        create_resources=True,
        cluster_id=cluster_id,
        access_cluster_ids=[cluster_id],
        filestore=V1FilestoreDataConnection(region=region, capacity_gb=capacity_gb, tier=tier, source=folder_name),
    )
    try:
        connection = client.data_connection_service_create_data_connection(body, project_id)
    except ApiException as e:
        # Note: This function can be called in a distributed way.
        # There is a race condition where one machine might create the entry before another machine
        # and this request would fail with duplicated key
        # In this case, it is fine not to raise
        if'duplicate key value violates unique constraint' in str(e.body):
            return
        raise e from None

    except urllib3.exceptions.HTTPError as e:
        raise e from None

    # Wait for the filesystem picks up the newly added Filestore folder
    start = time()

    while not os.path.isdir(f"/teamspace/filestore_folders/{folder_name}") and (time() - start) < create_timeout:
        sleep(1)


def create_cloud_agnostic_folder(folder_name: str, create_timeout: int = 30) -> None:
    """
    Utility function to create a Cloud-Agnostic (R2) folder.

    Args:
        folder_name: The name of the folder to create.
        create_timeout (int): The timeout for the folder creation.
    """
    client = rest_client.LightningClient(retry=False)

    project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID")
    cluster_id = os.getenv("LIGHTNING_CLUSTER_ID")

    # Get existing data connections
    data_connections = client.data_connection_service_list_data_connections(project_id).data_connections

    for connection in data_connections:
        existing_folder_name = getattr(connection, 'name', None)
        isCloudAgnostic = getattr(connection, 'r2_folder', None) is not None

        if existing_folder_name == folder_name and isCloudAgnostic:
            return

    # If we get here, no matching folder was found, proceed with creation
    body = Create(
        name=folder_name,
        create_resources=True,
        r2=V1R2DataConnection(name=folder_name),
    )
    try:
        connection = client.data_connection_service_create_data_connection(body, project_id)
    except ApiException as e:
        # Note: This function can be called in a distributed way.
        # There is a race condition where one machine might create the entry before another machine
        # and this request would fail with duplicated key
        # In this case, it is fine not to raise
        if'duplicate key value violates unique constraint' in str(e.body):
            return
        raise e from None

    except urllib3.exceptions.HTTPError as e:
        raise e from None

    # Wait for the filesystem picks up the newly added Cloud-Agnostic folder
    start = time()

    while not os.path.isdir(f"/teamspace/lightning_storage/{folder_name}") and (time() - start) < create_timeout:
        sleep(1)


def delete_data_connection(name: str):
    """Utility to delete a data connection

    Args:
        name: the name of the data connection to remove
    """
    client = rest_client.LightningClient(retry=False)

    project_id = os.getenv("LIGHTNING_CLOUD_PROJECT_ID")

    # Get existing data connections
    data_connections = client.data_connection_service_list_data_connections(project_id).data_connections

    data_connection_id = None

    for conn in data_connections:
        if conn.name == name:
            data_connection_id = conn.id
            break

    # data connection wasn't found
    if data_connection_id is None:
        return

    try:
        client.data_connection_service_delete_data_connection(project_id=project_id, id=data_connection_id)
    except ApiException as e:
        # TODO: with managed efs folders the contract around when it actually deletes is a bit fragile.
        #  It may exhaust the attempts before the connection is actually unmounted from the studio.
        #  for now it's best to actually stop the studio and all other things where the connection
        #  is mounted before trying to delete it
        raise e from None
