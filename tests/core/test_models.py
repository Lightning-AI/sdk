import os
from unittest import mock

import pytest

from lightning_sdk.lightning_cloud.openapi.models import (
    V1Membership,
    V1Organization,
    V1OwnerType,
    V1Project,
    V1SearchUser,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.models import _get_teamspace, download_model, upload_model
from lightning_sdk.user import User


@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.models._get_authed_user")
@mock.patch("lightning_sdk.models.UserApi")
@mock.patch("lightning_sdk.models.OrgApi")
def test_get_teamspace_org_owner(mock_org_api, mock_user_api, mock_get_authed_user, mock_teamspace_api):
    mock_user_api()._get_all_teamspace_memberships.return_value = [
        V1Membership(name="test-teamspace", owner_id="org-id", owner_type=V1OwnerType.ORGANIZATION),
        V1Membership(name="test-teamspace", owner_id="user-id", owner_type=V1OwnerType.USER),
        V1Membership(name="test-teamspace-2", owner_id="user-id", owner_type=V1OwnerType.USER),
    ]

    mock_org_api()._get_org_by_id.return_value = V1Organization(name="test-org")

    mock_get_authed_user.return_value.id = "user-id"

    mock_teamspace_api().get_teamspace.return_value = V1Project(name="test-teamspace")

    teamspace = _get_teamspace("test-teamspace", "test-org")

    assert teamspace.name == "test-teamspace"
    assert teamspace.owner.name == "test-org"

    mock_user_api()._get_all_teamspace_memberships.assert_called_once()
    mock_org_api()._get_org_by_id.assert_called_once_with("org-id")


@mock.patch("lightning_sdk.user.UserApi")
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.models._get_authed_user")
@mock.patch("lightning_sdk.models.UserApi")
@mock.patch("lightning_sdk.models.OrgApi")
def test_get_teamspace_authed_owner(
    mock_org_api, mock_user_api, mock_get_authed_user, mock_teamspace_api, mock_authed_user_api
):
    mock_user_api()._get_all_teamspace_memberships.return_value = [
        V1Membership(name="test-teamspace", owner_id="org-id", owner_type=V1OwnerType.ORGANIZATION),
        V1Membership(name="test-teamspace", owner_id="user-id", owner_type=V1OwnerType.USER),
        V1Membership(name="test-teamspace-2", owner_id="user-id", owner_type=V1OwnerType.USER),
    ]

    mock_org_api()._get_org_by_id.return_value = V1Organization(name="test-org")

    mock_authed_user_api().get_user.return_value.id = "user-id"
    mock_authed_user_api().get_user.return_value.username = "test-user"
    mock_get_authed_user.return_value = User("test-user")

    mock_teamspace_api().get_teamspace.return_value = V1Project(name="test-teamspace")

    teamspace = _get_teamspace("test-teamspace", "test-user")

    assert teamspace.name == "test-teamspace"
    assert teamspace.owner.name == "test-user"

    mock_user_api()._get_all_teamspace_memberships.assert_called_once()
    mock_org_api()._get_org_by_id.assert_called_once_with("org-id")


@mock.patch("lightning_sdk.user.UserApi")
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.models._get_authed_user")
@mock.patch("lightning_sdk.models.UserApi")
@mock.patch("lightning_sdk.models.OrgApi")
def test_get_teamspace_other_user_owner(
    mock_org_api, mock_user_api, mock_get_authed_user, mock_teamspace_api, mock_authed_user_api
):
    mock_user_api()._get_all_teamspace_memberships.return_value = [
        V1Membership(name="test-teamspace", owner_id="org-id", owner_type=V1OwnerType.ORGANIZATION),
        V1Membership(name="test-teamspace", owner_id="user-id", owner_type=V1OwnerType.USER),
        V1Membership(name="test-teamspace-2", owner_id="user-id-2", owner_type=V1OwnerType.USER),
    ]

    mock_org_api()._get_org_by_id.return_value = V1Organization(name="test-org")

    mock_user_api()._get_user_by_id.return_value = V1SearchUser(username="test-user-2")
    mock_authed_user_api().get_user.return_value.id = "user-id-2"
    mock_authed_user_api().get_user.return_value.username = "test-user-2"

    mock_get_authed_user.return_value.id = "user-id"

    mock_teamspace_api().get_teamspace.return_value = V1Project(name="test-teamspace-2")

    teamspace = _get_teamspace("test-teamspace-2", "test-user-2")

    assert teamspace.name == "test-teamspace-2"
    assert teamspace.owner.name == "test-user-2"

    mock_user_api()._get_all_teamspace_memberships.assert_called_once()
    mock_user_api()._get_user_by_id.assert_called_once_with("user-id-2")


@mock.patch("lightning_sdk.models.TeamspaceApi")
def test_download_model_errors(mock_teamspace_api):
    mock_teamspace_api().download_model_files.side_effect = ApiException(status=404)

    with pytest.raises(RuntimeError, match="Model 'owner/teamspace/model' not found"):
        download_model("owner/teamspace/model")

    with pytest.raises(RuntimeError, match="Model 'owner/teamspace/model:version' not found"):
        download_model("owner/teamspace/model:version")

    mock_teamspace_api().download_model_files.side_effect = ApiException(status=500)

    with pytest.raises(RuntimeError, match="Error downloading model. Status code: 500"):
        download_model("owner/teamspace/model")


@mock.patch.dict(os.environ, {"LIGHTNING_ORG": "org-abc", "LIGHTNING_TEAMSPACE": "ts-abc"})
@mock.patch("lightning_sdk.models._parse_model_name_and_version")
@mock.patch("lightning_sdk.api.teamspace_api._download_model_files")
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.organization.OrgApi")
def test_download_model_in_studio_with_org(
    mock_org_api, mock_teamspace_api, mock_download_model_files, mock_parse_model_name_and_version
):
    mock_parse_model_name_and_version.return_value = (mock.ANY, mock.ANY, mock.ANY, mock.ANY)
    mock_org_api().get_org.return_value = V1Organization(name="org-abc")
    mock_teamspace_api().get_teamspace.return_value = V1Project(name="ts-abc")

    download_model("model_name")
    mock_parse_model_name_and_version.assert_called_once_with("org-abc/ts-abc/model_name")


@mock.patch.dict(os.environ, {"LIGHTNING_USERNAME": "user-abc", "LIGHTNING_TEAMSPACE": "ts-abc"})
@mock.patch("lightning_sdk.models._parse_model_name_and_version")
@mock.patch("lightning_sdk.api.teamspace_api._download_model_files")
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.user.UserApi")
def test_download_model_in_studio_with_user(
    mock_user_api, mock_teamspace_api, mock_download_model_files, mock_parse_model_name_and_version
):
    mock_parse_model_name_and_version.return_value = (mock.ANY, mock.ANY, mock.ANY, mock.ANY)
    mock_teamspace_api().get_teamspace.return_value = V1Project(name="ts-abc")
    mock_user_api().get_user.return_value = V1SearchUser(username="user-abc")

    download_model("model_name")
    mock_parse_model_name_and_version.assert_called_once_with("user-abc/ts-abc/model_name")


@mock.patch.dict(os.environ, {"LIGHTNING_ORG": "org-abc", "LIGHTNING_TEAMSPACE": "ts-abc"})
@mock.patch("lightning_sdk.models._parse_model_name_and_version")
@mock.patch("lightning_sdk.models._get_teamspace")
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.organization.OrgApi")
def test_upload_model_in_studio_with_org(
    mock_org_api, mock_teamspace_api, mock_get_teamspace, mock_parse_model_name_and_version
):
    mock_parse_model_name_and_version.return_value = (mock.ANY, mock.ANY, mock.ANY, mock.ANY)
    mock_get_teamspace.return_value = mock.MagicMock()
    mock_org_api().get_org.return_value = V1Organization(name="org-abc")
    mock_teamspace_api().get_teamspace.return_value = V1Project(name="ts-abc")

    upload_model("model_name")
    mock_parse_model_name_and_version.assert_called_once_with("org-abc/ts-abc/model_name")


@mock.patch.dict(os.environ, {"LIGHTNING_USERNAME": "user-abc", "LIGHTNING_TEAMSPACE": "ts-abc"})
@mock.patch("lightning_sdk.models._parse_model_name_and_version")
@mock.patch("lightning_sdk.models._get_teamspace")
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.user.UserApi")
def test_upload_model_in_studio_with_user(
    mock_user_api, mock_teamspace_api, mock_get_teamspace, mock_parse_model_name_and_version
):
    mock_parse_model_name_and_version.return_value = (mock.ANY, mock.ANY, mock.ANY, mock.ANY)
    mock_get_teamspace.return_value = mock.MagicMock()
    mock_teamspace_api().get_teamspace.return_value = V1Project(name="ts-abc")
    mock_user_api().get_user.return_value = V1SearchUser(username="user-abc")

    upload_model("model_name")
    mock_parse_model_name_and_version.assert_called_once_with("user-abc/ts-abc/model_name")
