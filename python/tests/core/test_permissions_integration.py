"""Integration tests for permission checks across all SDK resources."""

from unittest import mock

import pytest

from lightning_sdk.lightning_cloud.openapi import V1Project, V1ProjectTab


@pytest.fixture(autouse=True)
def _clear_permission_cache():
    """Clear the permission cache before each test."""
    from lightning_sdk.api.utils import allowed_resource_access

    allowed_resource_access.cache_clear()
    yield
    allowed_resource_access.cache_clear()


# Teamspace property permission tests
@mock.patch("lightning_sdk.studio.Studio.__init__", return_value=None)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_teamspace_studios_property_raises_error_when_disabled(mock_teamspace_api, mock_studio_init):
    """Test that Teamspace.studios raises PermissionError when Studios permission is disabled."""
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Studios disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="studio", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project

    # Create a teamspace instance
    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    ts._teamspace_api = mock_teamspace_api.return_value

    with pytest.raises(PermissionError, match="Access to Studios has been disabled"):
        _ = ts.studios


@mock.patch("lightning_sdk.studio.Studio.__init__", return_value=None)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_teamspace_studios_property_succeeds_when_enabled(mock_teamspace_api, mock_studio_init):
    """Test that Teamspace.studios succeeds when Studios permission is enabled."""
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Studios enabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="studio", is_enabled=True)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project
    mock_teamspace_api.return_value.list_lightningapps.return_value = []

    # Create a teamspace instance
    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    ts._teamspace_api = mock_teamspace_api.return_value

    # Should not raise
    studios = ts.studios
    assert isinstance(studios, list)


@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_teamspace_vms_property_raises_error_with_vms_message(mock_teamspace_api):
    """Test that Teamspace.vms raises PermissionError with 'VMs' in message when Studios permission is disabled."""
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Studios disabled (VMs uses Studios permission)
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="studio", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project

    # Create a teamspace instance
    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    ts._teamspace_api = mock_teamspace_api.return_value

    # VMs should have "VMs" in the error message, not "Studios"
    with pytest.raises(PermissionError, match="Access to VMs has been disabled"):
        _ = ts.vms


@mock.patch("lightning_sdk.job.Job.__init__", return_value=None)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_teamspace_jobs_property_raises_error_when_disabled(mock_teamspace_api, mock_job_init):
    """Test that Teamspace.jobs raises PermissionError when Jobs permission is disabled."""
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Jobs disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="jobs", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project

    # Create a teamspace instance
    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    ts._teamspace_api = mock_teamspace_api.return_value

    with pytest.raises(PermissionError, match="Access to Jobs has been disabled"):
        _ = ts.jobs


@mock.patch("lightning_sdk.job.Job.__init__", return_value=None)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_teamspace_jobs_property_succeeds_when_enabled(mock_teamspace_api, mock_job_init):
    """Test that Teamspace.jobs succeeds when Jobs permission is enabled."""
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Jobs enabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="jobs", is_enabled=True)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project
    mock_teamspace_api.return_value.list_jobs.return_value = ([], [])

    # Create a teamspace instance
    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    ts._teamspace_api = mock_teamspace_api.return_value

    # Should not raise
    jobs = ts.jobs
    assert isinstance(jobs, tuple)


@mock.patch("lightning_sdk.mmt.MMT.__init__", return_value=None)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_teamspace_multi_machine_jobs_property_raises_error_when_disabled(mock_teamspace_api, mock_mmt_init):
    """Test that Teamspace.multi_machine_jobs raises PermissionError when Jobs permission is disabled."""
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Jobs disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="jobs", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project
    mock_teamspace_api.return_value._get_authed_user_id.return_value = "test-user-id"

    # Create a teamspace instance
    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    ts._teamspace_api = mock_teamspace_api.return_value

    with pytest.raises(PermissionError, match="Access to Jobs has been disabled"):
        _ = ts.multi_machine_jobs


@mock.patch("lightning_sdk.mmt.MMT.__init__", return_value=None)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_teamspace_multi_machine_jobs_property_succeeds_when_enabled(mock_teamspace_api, mock_mmt_init):
    """Test that Teamspace.multi_machine_jobs succeeds when Jobs permission is enabled."""
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Jobs enabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="jobs", is_enabled=True)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project
    mock_teamspace_api.return_value.list_mmts.return_value = ([], [])

    # Create a teamspace instance
    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    ts._teamspace_api = mock_teamspace_api.return_value

    # Should not raise
    mmts = ts.multi_machine_jobs
    assert isinstance(mmts, tuple)


# Studio class permission tests
@mock.patch("lightning_sdk.user.UserApi")
@mock.patch("lightning_sdk.studio._resolve_teamspace")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_studio_init_raises_error_when_studios_disabled(mock_teamspace_api, mock_resolve_teamspace, mock_user_api):
    """Test that Studio.__init__ raises PermissionError when Studios permission is disabled."""
    from lightning_sdk.lightning_cloud.openapi.models import V1SearchUser
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

    # Mock the teamspace with Studios disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="studio", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project
    mock_teamspace_api.return_value._get_authed_user_id.return_value = "test-user-id"
    mock_user_api().get_user.return_value = V1SearchUser(username="test-user")

    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    ts._teamspace_api = mock_teamspace_api.return_value
    ts._owner = User("test-user")
    mock_resolve_teamspace.return_value = ts

    with pytest.raises(PermissionError, match="Access to Studios has been disabled"):
        Studio(name="test-studio")


# Job class permission tests
@mock.patch("lightning_sdk.job.job._resolve_teamspace")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_job_init_raises_error_when_jobs_disabled(mock_teamspace_api, mock_resolve_teamspace):
    """Test that Job.__init__ raises PermissionError when Jobs permission is disabled."""
    from lightning_sdk.job import Job
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Jobs disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="jobs", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project

    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    mock_resolve_teamspace.return_value = ts

    with pytest.raises(PermissionError, match="Access to Jobs has been disabled"):
        Job(name="test-job")


# MMT class permission tests
@mock.patch("lightning_sdk.mmt.mmt._resolve_teamspace")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_mmt_init_raises_error_when_jobs_disabled(mock_teamspace_api, mock_resolve_teamspace):
    """Test that MMT.__init__ raises PermissionError when Jobs permission is disabled."""
    from lightning_sdk.mmt import MMT
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Jobs disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="jobs", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project

    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    mock_resolve_teamspace.return_value = ts

    with pytest.raises(PermissionError, match="Access to Jobs has been disabled"):
        MMT(name="test-mmt")


# Pipeline class permission tests
@mock.patch("lightning_sdk.pipeline.pipeline._resolve_teamspace")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_pipeline_init_raises_error_when_pipelines_disabled(mock_teamspace_api, mock_resolve_teamspace):
    """Test that Pipeline.__init__ raises PermissionError when Pipelines permission is disabled."""
    from lightning_sdk.pipeline import Pipeline
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Pipelines disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="pipelines", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project

    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    mock_resolve_teamspace.return_value = ts

    with pytest.raises(PermissionError, match="Access to Pipelines has been disabled"):
        Pipeline(name="test-pipeline")


# Deployment class permission tests
@mock.patch("lightning_sdk.lightning_cloud.login.Auth")
@mock.patch("lightning_sdk.user.UserApi")
@mock.patch("lightning_sdk.deployment.deployment._resolve_teamspace")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@mock.patch("lightning_sdk.deployment.deployment._get_cluster")
@pytest.mark.project_permission_test()
def test_deployment_init_raises_error_when_deployments_disabled(
    mock_get_cluster, mock_teamspace_api, mock_resolve_teamspace, mock_user_api, mock_auth
):
    """Test that Deployment.__init__ raises PermissionError when Deployments permission is disabled."""
    from lightning_sdk.deployment import Deployment
    from lightning_sdk.lightning_cloud.openapi.models import V1SearchUser
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

    # Mock the teamspace with Deployments disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="deployments", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project
    mock_teamspace_api.return_value._get_authed_user_id.return_value = "test-user-id"
    mock_user_api().get_user.return_value = V1SearchUser(username="test-user")

    # Mock Auth to prevent authentication calls
    mock_auth_instance = mock_auth.return_value
    mock_auth_instance.user_id = "test-user-id"
    mock_auth_instance.authenticate.return_value = None

    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    ts._teamspace_api = mock_teamspace_api.return_value
    ts._owner = User("test-user")
    mock_resolve_teamspace.return_value = ts

    with pytest.raises(PermissionError, match="Access to Deployments has been disabled"):
        Deployment(name="test-deployment")


# LitContainer class permission tests
@mock.patch("lightning_sdk.lit_container._resolve_teamspace")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_litcontainer_list_raises_error_when_containers_disabled(mock_teamspace_api, mock_resolve_teamspace):
    """Test that LitContainer.list_containers() raises PermissionError when Containers permission is disabled."""
    from lightning_sdk.lit_container import LitContainer
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Containers disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="containers", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project

    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    mock_resolve_teamspace.return_value = ts

    container = LitContainer()

    with pytest.raises(PermissionError, match="Access to Containers has been disabled"):
        container.list_containers(teamspace="test-teamspace")


@mock.patch("lightning_sdk.lit_container._resolve_teamspace")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_litcontainer_delete_raises_error_when_containers_disabled(mock_teamspace_api, mock_resolve_teamspace):
    """Test that LitContainer.delete_container() raises PermissionError when Containers permission is disabled."""
    from lightning_sdk.lit_container import LitContainer
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Containers disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="containers", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project

    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    mock_resolve_teamspace.return_value = ts

    container = LitContainer()

    with pytest.raises(PermissionError, match="Access to Containers has been disabled"):
        container.delete_container(container="test-container", teamspace="test-teamspace")


@mock.patch("lightning_sdk.lit_container._resolve_teamspace")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_litcontainer_upload_raises_error_when_containers_disabled(mock_teamspace_api, mock_resolve_teamspace):
    """Test that LitContainer.upload_container() raises PermissionError when Containers permission is disabled."""
    from lightning_sdk.lit_container import LitContainer
    from lightning_sdk.teamspace import Teamspace

    # Mock the teamspace with Containers disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="containers", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project

    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    mock_resolve_teamspace.return_value = ts

    container = LitContainer()

    with pytest.raises(PermissionError, match="Access to Containers has been disabled"):
        container.upload_container(container="test-container", teamspace="test-teamspace")


@mock.patch("lightning_sdk.user.UserApi")
@mock.patch("lightning_sdk.lit_container._resolve_teamspace")
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi")
@pytest.mark.project_permission_test()
def test_litcontainer_download_raises_error_when_containers_disabled(
    mock_teamspace_api, mock_resolve_teamspace, mock_user_api
):
    """Test that LitContainer.download_container() raises PermissionError when Containers permission is disabled."""
    from lightning_sdk.lightning_cloud.openapi.models import V1SearchUser
    from lightning_sdk.lit_container import LitContainer
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

    # Mock the teamspace with Containers disabled
    mock_project = V1Project(
        id="test-teamspace-id",
        name="test-teamspace",
        layout_config=[V1ProjectTab(slug="containers", is_enabled=False)],
    )

    mock_teamspace_api.return_value.get_teamspace.return_value = mock_project
    mock_teamspace_api.return_value._get_teamspace_by_id.return_value = mock_project
    mock_teamspace_api.return_value._get_authed_user_id.return_value = "test-user-id"
    mock_user_api().get_user.return_value = V1SearchUser(username="test-user")

    ts = Teamspace.__new__(Teamspace)
    ts._teamspace = mock_project
    ts._teamspace_api = mock_teamspace_api.return_value
    ts._owner = User("test-user")
    mock_resolve_teamspace.return_value = ts

    container = LitContainer()

    with pytest.raises(PermissionError, match="Access to Containers has been disabled"):
        container.download_container(container="test-container", teamspace="test-teamspace")
