from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from lightning_sdk.api.teamspace_api import TeamspaceApi
from lightning_sdk.data_connection import BucketCredentials
from lightning_sdk.lightning_cloud.openapi import (
    V1DataConnection,
    V1GetTempBucketCredentialsResponse,
    V1ListDataConnectionsResponse,
)


def _api_with_connections(*connections, credentials=None):
    """Build a TeamspaceApi whose generated client is mocked out."""
    with mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock()):
        api = TeamspaceApi()

    client = mock.MagicMock()
    client.data_connection_service_list_data_connections.return_value = V1ListDataConnectionsResponse(
        data_connections=list(connections)
    )
    if credentials is not None:
        client.data_connection_service_get_temp_bucket_credentials.return_value = credentials
    api._client = client
    return api, client


def test_resolves_a_connection_id_from_its_name():
    api, _ = _api_with_connections(
        V1DataConnection(id="dc-1", name="training-data"),
        V1DataConnection(id="dc-2", name="checkpoints"),
    )

    assert api.resolve_data_connection_id("ts-1", "checkpoints") == "dc-2"


def test_unknown_connection_name_lists_the_ones_that_exist():
    api, _ = _api_with_connections(
        V1DataConnection(id="dc-1", name="training-data"),
        V1DataConnection(id="dc-2", name="checkpoints"),
    )

    # The available names are the whole value of the error: the caller passed a name,
    # so an ID they cannot see would tell them nothing about what to pass instead.
    with pytest.raises(ValueError, match="checkpoints, training-data"):
        api.resolve_data_connection_id("ts-1", "nope")


def test_no_connections_at_all_is_not_a_crash():
    """An empty teamspace returns no list at all, rather than an empty one."""
    with mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock()):
        api = TeamspaceApi()
    client = mock.MagicMock()
    client.data_connection_service_list_data_connections.return_value = V1ListDataConnectionsResponse(
        data_connections=None
    )
    api._client = client

    with pytest.raises(ValueError, match="Available connections: none"):
        api.resolve_data_connection_id("ts-1", "anything")


def test_credentials_carry_the_region_and_endpoint_they_are_scoped_to():
    expires_at = datetime(2026, 9, 9, 22, 0, tzinfo=timezone.utc)
    api, client = _api_with_connections(
        V1DataConnection(id="dc-1", name="training-data"),
        credentials=V1GetTempBucketCredentialsResponse(
            access_key_id="AKIA",
            secret_access_key="secret",
            session_token="token",
            expires_at=expires_at,
            region="us-west-2",
            endpoint="https://s3.us-west-2.amazonaws.com",
        ),
    )

    credentials = api.get_temp_bucket_credentials("ts-1", "training-data")

    assert credentials == BucketCredentials(
        access_key_id="AKIA",
        secret_access_key="secret",
        session_token="token",
        expires_at=expires_at,
        region="us-west-2",
        endpoint="https://s3.us-west-2.amazonaws.com",
    )
    client.data_connection_service_get_temp_bucket_credentials.assert_called_once_with("ts-1", "dc-1")


def test_credential_process_payload_matches_what_aws_expects():
    expires_at = datetime(2026, 9, 9, 22, 0, tzinfo=timezone.utc)
    credentials = BucketCredentials(
        access_key_id="AKIA",
        secret_access_key="secret",
        session_token="token",
        expires_at=expires_at,
        region="us-west-2",
    )

    assert credentials.to_credential_process() == {
        "Version": 1,
        "AccessKeyId": "AKIA",
        "SecretAccessKey": "secret",
        "SessionToken": "token",
        "Expiration": "2026-09-09T22:00:00+00:00",
    }


def test_static_key_connections_report_no_expiration():
    """A connection backed by static keys has no deadline, and AWS reads that as never."""
    credentials = BucketCredentials(access_key_id="AKIA", secret_access_key="secret")

    payload = credentials.to_credential_process()

    assert "Expiration" not in payload
    assert "SessionToken" not in payload


def test_a_naive_expiry_is_read_as_utc_not_local_time():
    """The control plane reports UTC, so a naive value must not be read as local time.

    Converting one west of UTC pushes the deadline hours later than it really is, and
    the tool sits on an expired credential instead of refreshing.
    """
    credentials = BucketCredentials(
        access_key_id="AKIA",
        secret_access_key="secret",
        expires_at=datetime(2026, 9, 9, 22, 0),
    )

    expiration = credentials.to_credential_process()["Expiration"]

    assert expiration == "2026-09-09T22:00:00+00:00"


def test_a_non_utc_expiry_keeps_the_same_instant():
    credentials = BucketCredentials(
        access_key_id="AKIA",
        secret_access_key="secret",
        expires_at=datetime(2026, 9, 9, 22, 0, tzinfo=timezone(timedelta(hours=-7))),
    )

    assert credentials.to_credential_process()["Expiration"] == "2026-09-10T05:00:00+00:00"
