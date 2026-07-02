from unittest import mock

import pytest

from lightning_sdk.api.utils import AccessibleResource, allowed_resource_access, raise_access_error_if_not_allowed
from lightning_sdk.lightning_cloud.openapi import V1Project, V1ProjectTab


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the LRU cache before each test to ensure test isolation."""
    allowed_resource_access.cache_clear()
    yield
    allowed_resource_access.cache_clear()


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_allowed_resource_access_when_tab_enabled(mock_teamspace_api):
    """Test that allowed_resource_access returns True when the tab is enabled."""
    teamspace_id = "test-teamspace-id"
    resource_type = AccessibleResource.Studios

    # Mock the teamspace with layout_config where Studios is enabled
    mock_teamspace = V1Project(
        id=teamspace_id,
        name="test-teamspace",
        layout_config=[
            V1ProjectTab(slug="studio", is_enabled=True),
            V1ProjectTab(slug="jobs", is_enabled=False),
        ],
    )

    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_teamspace

    result = allowed_resource_access(resource_type, teamspace_id)

    assert result is True
    mock_teamspace_api.return_value._get_teamspace_by_id.assert_called_once_with(teamspace_id=teamspace_id)


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_allowed_resource_access_when_tab_disabled(mock_teamspace_api):
    """Test that allowed_resource_access returns False when the tab is disabled."""
    teamspace_id = "test-teamspace-id"
    resource_type = AccessibleResource.Jobs

    # Mock the teamspace with layout_config where Jobs is disabled
    mock_teamspace = V1Project(
        id=teamspace_id,
        name="test-teamspace",
        layout_config=[
            V1ProjectTab(slug="studio", is_enabled=True),
            V1ProjectTab(slug="jobs", is_enabled=False),
        ],
    )

    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_teamspace

    result = allowed_resource_access(resource_type, teamspace_id)

    assert result is False
    mock_teamspace_api.return_value._get_teamspace_by_id.assert_called_once_with(teamspace_id=teamspace_id)


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_allowed_resource_access_when_tab_not_found_allows_by_default(mock_teamspace_api):
    """Test that allowed_resource_access returns True when the tab is not found (backwards compatibility)."""
    teamspace_id = "test-teamspace-id"
    resource_type = AccessibleResource.Models

    # Mock the teamspace with layout_config that doesn't include Models
    mock_teamspace = V1Project(
        id=teamspace_id,
        name="test-teamspace",
        layout_config=[
            V1ProjectTab(slug="studio", is_enabled=True),
            V1ProjectTab(slug="jobs", is_enabled=True),
        ],
    )

    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_teamspace

    result = allowed_resource_access(resource_type, teamspace_id)

    assert result is True
    mock_teamspace_api.return_value._get_teamspace_by_id.assert_called_once_with(teamspace_id=teamspace_id)


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_allowed_resource_access_with_empty_layout_config(mock_teamspace_api):
    """Test that allowed_resource_access returns True when layout_config is empty."""
    teamspace_id = "test-teamspace-id"
    resource_type = AccessibleResource.Deployments

    # Mock the teamspace with empty layout_config
    mock_teamspace = V1Project(
        id=teamspace_id,
        name="test-teamspace",
        layout_config=[],
    )

    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_teamspace

    result = allowed_resource_access(resource_type, teamspace_id)

    assert result is True
    mock_teamspace_api.return_value._get_teamspace_by_id.assert_called_once_with(teamspace_id=teamspace_id)


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_allowed_resource_access_with_none_layout_config(mock_teamspace_api):
    """Test that allowed_resource_access returns True when layout_config is None."""
    teamspace_id = "test-teamspace-id"
    resource_type = AccessibleResource.Pipelines

    # Mock the teamspace with None layout_config
    mock_teamspace = V1Project(
        id=teamspace_id,
        name="test-teamspace",
        layout_config=None,
    )

    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_teamspace

    result = allowed_resource_access(resource_type, teamspace_id)

    assert result is True
    mock_teamspace_api.return_value._get_teamspace_by_id.assert_called_once_with(teamspace_id=teamspace_id)


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_allowed_resource_access_caching(mock_teamspace_api):
    """Test that allowed_resource_access caches results using lru_cache."""
    teamspace_id = "test-teamspace-id"
    resource_type = AccessibleResource.Studios

    # Mock the teamspace
    mock_teamspace = V1Project(
        id=teamspace_id,
        name="test-teamspace",
        layout_config=[
            V1ProjectTab(slug="studio", is_enabled=True),
        ],
    )

    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_teamspace

    # Call the function twice with the same arguments
    result1 = allowed_resource_access(resource_type, teamspace_id)
    result2 = allowed_resource_access(resource_type, teamspace_id)

    assert result1 is True
    assert result2 is True
    # Should only be called once due to caching
    mock_teamspace_api.return_value._get_teamspace_by_id.assert_called_once_with(teamspace_id=teamspace_id)


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.parametrize(
    "resource_type",
    [
        AccessibleResource.Studios,
        AccessibleResource.Drive,
        AccessibleResource.Jobs,
        AccessibleResource.Deployments,
        AccessibleResource.Pipelines,
        AccessibleResource.Models,
        AccessibleResource.Containers,
        AccessibleResource.Settings,
    ],
)
@pytest.mark.project_permission_test()
def test_allowed_resource_access_all_resource_types(mock_teamspace_api, resource_type):
    """Test allowed_resource_access with all AccessibleResource types."""
    teamspace_id = "test-teamspace-id"

    # Mock the teamspace with all tabs enabled
    mock_teamspace = V1Project(
        id=teamspace_id,
        name="test-teamspace",
        layout_config=[
            V1ProjectTab(slug=str(resource_type), is_enabled=True),
        ],
    )

    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_teamspace

    result = allowed_resource_access(resource_type, teamspace_id)

    assert result is True


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_raise_access_error_when_access_not_allowed(mock_teamspace_api):
    """Test that raise_access_error_if_not_allowed raises PermissionError when access is not allowed."""
    teamspace_id = "test-teamspace-id"
    resource_type = AccessibleResource.Jobs

    # Mock the teamspace with Jobs disabled
    mock_teamspace = V1Project(
        id=teamspace_id,
        name="test-teamspace",
        layout_config=[
            V1ProjectTab(slug="jobs", is_enabled=False),
        ],
    )

    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_teamspace

    with pytest.raises(
        PermissionError,
        match="Access to Jobs has been disabled for this teamspace. Contact a teamspace administrator to enable it.",
    ):
        raise_access_error_if_not_allowed(resource_type, teamspace_id)

    mock_teamspace_api.return_value._get_teamspace_by_id.assert_called_once_with(teamspace_id=teamspace_id)


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_raise_access_error_does_not_raise_when_access_allowed(mock_teamspace_api):
    """Test that raise_access_error_if_not_allowed does not raise when access is allowed."""
    teamspace_id = "test-teamspace-id"
    resource_type = AccessibleResource.Studios

    # Mock the teamspace with Studios enabled
    mock_teamspace = V1Project(
        id=teamspace_id,
        name="test-teamspace",
        layout_config=[
            V1ProjectTab(slug="studio", is_enabled=True),
        ],
    )

    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_teamspace

    # Should not raise any exception
    raise_access_error_if_not_allowed(resource_type, teamspace_id)

    mock_teamspace_api.return_value._get_teamspace_by_id.assert_called_once_with(teamspace_id=teamspace_id)


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_raise_access_error_does_not_raise_when_tab_not_found(mock_teamspace_api):
    """Test that raise_access_error_if_not_allowed does not raise when tab is not in config (backwards compat)."""
    teamspace_id = "test-teamspace-id"
    resource_type = AccessibleResource.Models

    # Mock the teamspace without Models in layout_config
    mock_teamspace = V1Project(
        id=teamspace_id,
        name="test-teamspace",
        layout_config=[
            V1ProjectTab(slug="studio", is_enabled=True),
        ],
    )

    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_teamspace

    # Should not raise any exception (backwards compatibility)
    raise_access_error_if_not_allowed(resource_type, teamspace_id)

    mock_teamspace_api.return_value._get_teamspace_by_id.assert_called_once_with(teamspace_id=teamspace_id)


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.parametrize(
    ("resource_type", "expected_message"),
    [
        (AccessibleResource.Studios, "Access to Studios has been disabled"),
        (AccessibleResource.Drive, "Access to Drive has been disabled"),
        (AccessibleResource.Jobs, "Access to Jobs has been disabled"),
        (AccessibleResource.Deployments, "Access to Deployments has been disabled"),
        (AccessibleResource.Pipelines, "Access to Pipelines has been disabled"),
        (AccessibleResource.Models, "Access to Models has been disabled"),
        (AccessibleResource.Containers, "Access to Containers has been disabled"),
        (AccessibleResource.Settings, "Access to Settings has been disabled"),
    ],
)
@pytest.mark.project_permission_test()
def test_raise_access_error_messages_for_all_resources(mock_teamspace_api, resource_type, expected_message):
    """Test that raise_access_error_if_not_allowed raises correct error messages for all resource types."""
    teamspace_id = "test-teamspace-id"

    # Mock the teamspace with the specific resource disabled
    mock_teamspace = V1Project(
        id=teamspace_id,
        name="test-teamspace",
        layout_config=[
            V1ProjectTab(slug=str(resource_type), is_enabled=False),
        ],
    )

    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_teamspace

    with pytest.raises(PermissionError, match=expected_message):
        raise_access_error_if_not_allowed(resource_type, teamspace_id)


def test_accessible_resource_string_representation():
    """Test that AccessibleResource enum converts to string correctly."""
    assert str(AccessibleResource.Studios) == "studio"
    assert str(AccessibleResource.Drive) == "drive"
    assert str(AccessibleResource.Jobs) == "jobs"
    assert str(AccessibleResource.Deployments) == "deployments"
    assert str(AccessibleResource.Pipelines) == "pipelines"
    assert str(AccessibleResource.Models) == "models"
    assert str(AccessibleResource.Containers) == "containers"
    assert str(AccessibleResource.Settings) == "settings"


def test_accessible_resource_repr():
    """Test that AccessibleResource enum repr returns correct value."""
    assert repr(AccessibleResource.Studios) == "studio"
    assert repr(AccessibleResource.Jobs) == "jobs"


def test_accessible_resource_equality_with_string():
    """Test that AccessibleResource can be compared with strings."""
    assert AccessibleResource.Studios == "studio"
    assert AccessibleResource.Jobs == "jobs"
    assert AccessibleResource.Models == "models"


def test_accessible_resource_equality_with_enum():
    """Test that AccessibleResource can be compared with other enum instances."""
    assert AccessibleResource.Studios == AccessibleResource.Studios
    assert AccessibleResource.Jobs == AccessibleResource.Jobs
    assert AccessibleResource.Studios != AccessibleResource.Jobs


def test_accessible_resource_hash():
    """Test that AccessibleResource can be used in sets and as dict keys."""
    resource_set = {AccessibleResource.Studios, AccessibleResource.Jobs, AccessibleResource.Studios}
    assert len(resource_set) == 2

    resource_dict = {
        AccessibleResource.Studios: "studio_value",
        AccessibleResource.Jobs: "jobs_value",
    }
    assert resource_dict[AccessibleResource.Studios] == "studio_value"
    assert resource_dict[AccessibleResource.Jobs] == "jobs_value"
