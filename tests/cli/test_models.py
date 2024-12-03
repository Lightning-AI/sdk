from unittest import mock
from lightning_sdk.cli.models import _get_teamspace
from lightning_sdk.user import User
from lightning_sdk.lightning_cloud.openapi.models import V1Membership, V1OwnerType, V1Organization, V1Project, V1SearchUser

@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.cli.models._get_authed_user")
@mock.patch("lightning_sdk.cli.models.UserApi")
@mock.patch("lightning_sdk.cli.models.OrgApi")
def test_get_teamspace_org_owner(mock_org_api, mock_user_api, mock_get_authed_user, mock_teamspace_api):
    mock_user_api()._get_all_teamspace_memberships.return_value = [
        V1Membership(name="test-teamspace", owner_id="org-id", owner_type=V1OwnerType.ORGANIZATION),
        V1Membership(name="test-teamspace", owner_id="user-id", owner_type=V1OwnerType.USER),
        V1Membership(name="test-teamspace-2", owner_id="user-id", owner_type=V1OwnerType.USER),
    ]

    mock_org_api()._get_org_by_id.return_value = V1Organization(name="test-org")

    mock_get_authed_user.return_value.id = "user-id"

    mock_teamspace_api().get_teamspace.return_value = V1Project(name = "test-teamspace")

    teamspace = _get_teamspace("test-teamspace", "test-org")

    assert teamspace.name == "test-teamspace"
    assert teamspace.owner.name == "test-org"

    mock_user_api()._get_all_teamspace_memberships.assert_called_once()
    mock_org_api()._get_org_by_id.assert_called_once_with("org-id")


@mock.patch("lightning_sdk.user.UserApi")
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.cli.models._get_authed_user")
@mock.patch("lightning_sdk.cli.models.UserApi")
@mock.patch("lightning_sdk.cli.models.OrgApi")
def test_get_teamspace_authed_owner(mock_org_api, mock_user_api, mock_get_authed_user, mock_teamspace_api, mock_authed_user_api):
    mock_user_api()._get_all_teamspace_memberships.return_value = [
        V1Membership(name="test-teamspace", owner_id="org-id", owner_type=V1OwnerType.ORGANIZATION),
        V1Membership(name="test-teamspace", owner_id="user-id", owner_type=V1OwnerType.USER),
        V1Membership(name="test-teamspace-2", owner_id="user-id", owner_type=V1OwnerType.USER),
    ]

    mock_org_api()._get_org_by_id.return_value = V1Organization(name="test-org")

    mock_authed_user_api().get_user.return_value.id = "user-id"
    mock_authed_user_api().get_user.return_value.username = "test-user"
    mock_get_authed_user.return_value = User("test-user")

    mock_teamspace_api().get_teamspace.return_value = V1Project(name = "test-teamspace")

    teamspace = _get_teamspace("test-teamspace", "test-user")

    assert teamspace.name == "test-teamspace"
    assert teamspace.owner.name == "test-user"

    mock_user_api()._get_all_teamspace_memberships.assert_called_once()
    mock_org_api()._get_org_by_id.assert_called_once_with("org-id")


@mock.patch("lightning_sdk.user.UserApi")
@mock.patch("lightning_sdk.teamspace.TeamspaceApi")
@mock.patch("lightning_sdk.cli.models._get_authed_user")
@mock.patch("lightning_sdk.cli.models.UserApi")
@mock.patch("lightning_sdk.cli.models.OrgApi")
def test_get_teamspace_other_user_owner(mock_org_api, mock_user_api, mock_get_authed_user, mock_teamspace_api, mock_authed_user_api):
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

    mock_teamspace_api().get_teamspace.return_value = V1Project(name = "test-teamspace-2")

    teamspace = _get_teamspace("test-teamspace-2", "test-user-2")

    assert teamspace.name == "test-teamspace-2"
    assert teamspace.owner.name == "test-user-2"

    mock_user_api()._get_all_teamspace_memberships.assert_called_once()
    mock_user_api()._get_user_by_id.assert_called_once_with("user-id-2")
