from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.api.lit_container_api import LitContainerApi
from lightning_sdk.lit_container import LitContainer


@pytest.fixture()
def mock_teamspace():
    teamspace = MagicMock()
    teamspace.id = "test-project-id"
    teamspace.owner.name = "test-org"
    return teamspace


@pytest.fixture()
def mock_api_list_containers():
    repo = MagicMock()
    repo.name = "test-docker-image"
    repo.id = "test-image-id"
    repo.creation_time = datetime(2024, 1, 1, 12, 0, 0)
    return repo


def test_list_containers(mock_teamspace, mock_api_list_containers):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve_teamspace:
        mock_resolve_teamspace.return_value = mock_teamspace

        registry = LitContainer()
        registry._api = MagicMock(spec=LitContainerApi)
        registry._api.list_containers.return_value = [mock_api_list_containers]

        result = registry.list_containers(teamspace="test-teamspace")

        mock_resolve_teamspace.assert_called_once_with(teamspace="test-teamspace", org=None, user=None)
        registry._api.list_containers.assert_called_once_with("test-project-id")

        expected_result = [
            {"REPOSITORY": "test-docker-image", "IMAGE ID": "test-image-id", "CREATED": "2024-01-01 12:00:00"}
        ]
        assert result == expected_result


def test_list_containers_with_org(mock_teamspace, mock_api_list_containers):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve_teamspace:
        mock_resolve_teamspace.return_value = mock_teamspace

        registry = LitContainer()
        registry._api = MagicMock(spec=LitContainerApi)
        registry._api.list_containers.return_value = [mock_api_list_containers]

        result = registry.list_containers(teamspace="test-teamspace", org="test-org")

        mock_resolve_teamspace.assert_called_once_with(teamspace="test-teamspace", org="test-org", user=None)
        registry._api.list_containers.assert_called_once_with("test-project-id")

        expected_result = [
            {"REPOSITORY": "test-docker-image", "IMAGE ID": "test-image-id", "CREATED": "2024-01-01 12:00:00"}
        ]
        assert result == expected_result


def test_delete_container(mock_teamspace):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve_teamspace:
        mock_resolve_teamspace.return_value = mock_teamspace

        registry = LitContainer()
        registry._api = MagicMock(spec=LitContainerApi)
        registry._api.delete_container.return_value = None

        registry.delete_container("test-repo", "test-teamspace", "test-org", None)

        mock_resolve_teamspace.assert_called_once_with(teamspace="test-teamspace", org="test-org", user=None)
        registry._api.delete_container.assert_called_once_with("test-project-id", "test-repo")


@pytest.fixture()
def lit_container():
    return LitContainer()


def test_upload_container_success(lit_container, mock_teamspace):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve, patch.object(
        lit_container._api, "upload_container"
    ) as mock_upload:
        # Setup mocks
        mock_resolve.return_value = mock_teamspace
        mock_upload.return_value = ["Uploading...", "Upload complete"]

        # Call the method
        lit_container.upload_container(container="my-container", teamspace="test-team", tag="v1.0")

        # Verify the mocks were called correctly
        mock_resolve.assert_called_once_with(teamspace="test-team", org=None, user=None)
        mock_upload.assert_called_once_with("my-container", mock_teamspace, "v1.0")


def test_upload_container_teamspace_resolution_error(lit_container):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve:
        # Setup mock to raise an exception
        mock_resolve.side_effect = Exception("Invalid teamspace")

        # Verify that the correct exception is raised
        with pytest.raises(ValueError, match="Could not resolve teamspace: Invalid teamspace"):
            lit_container.upload_container(container="my-container", teamspace="invalid-team")


def test_upload_container_with_org(lit_container, mock_teamspace):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve, patch.object(
        lit_container._api, "upload_container"
    ) as mock_upload:
        # Setup mocks
        mock_resolve.return_value = mock_teamspace
        mock_upload.return_value = ["Uploading...", "Upload complete"]

        # Call the method with org parameter
        lit_container.upload_container(container="my-container", teamspace="test-team", org="test-org", tag="latest")

        # Verify the mocks were called correctly
        mock_resolve.assert_called_once_with(teamspace="test-team", org="test-org", user=None)
        mock_upload.assert_called_once_with("my-container", mock_teamspace, "latest")


def test_download_container(lit_container, mock_teamspace):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve, patch.object(
        lit_container._api, "_docker_client"
    ) as mock_docker_client:
        mock_resolve.return_value = mock_teamspace

        lit_container.download_container(container="my-container", teamspace="test-team", tag="latest")
        mock_docker_client.images.pull.assert_called_once(), "Docker pull was not called"


@patch("lightning_sdk.api.lit_container_api.docker")
@patch("lightning_sdk.api.lit_container_api.LightningClient")
def test_authenticate(mock_lightning_client, mock_docker):
    api = LitContainerApi()
    mock_lightning_client.auth_service_get_user.return_value = MagicMock(username="test-user", api_key="test-key")
    api.authenticate()
    mock_docker.from_env.assert_called(), "Docker client was not created"
    mock_docker.from_env().login.assert_called(), "Docker client was not created"
