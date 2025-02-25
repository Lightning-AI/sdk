from datetime import datetime
from unittest.mock import MagicMock, call, patch

import docker.errors
import pytest

from lightning_sdk.api.lit_container_api import DockerPushError, LitContainerApi
from lightning_sdk.api.utils import _get_registry_url
from lightning_sdk.lit_container import LitContainer


@pytest.fixture()
def mock_teamspace():
    teamspace = MagicMock()
    teamspace.id = "test-project-id"
    teamspace.owner.name = "test-org"
    teamspace.name = "test-team"
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


def test_upload_container_pull_then_push(lit_container, mock_teamspace):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve, patch.object(
        lit_container._api, "_docker_client"
    ) as mock_docker_client:
        mock_resolve.return_value = mock_teamspace

        lit_container._api._docker_auth_config = {"username": "admin", "api_key": "grid"}
        mock_docker_client.images.get.side_effect = [
            docker.errors.ImageNotFound("This will trigger images.pull()"),
            MagicMock(id="my-container"),
        ]
        mock_docker_client.images.pull.return_value = MagicMock(id="my-container")
        mock_docker_client.api.tag.return_value = True
        mock_docker_client.api.push.return_value = [{"status": "Pushing"}, {"status": "Complete"}]

        lit_container.upload_container(container="my-container", teamspace="test-team", tag="v1.0")

        mock_resolve.assert_called_once_with(teamspace="test-team", org=None, user=None)

        # Assert that we call get(my-container) on the first attempt
        # Assert that we call get(my-container) on the second attempt after pull
        mock_docker_client.images.get.assert_has_calls([call("my-container"), call("my-container")])

        # Assert we fallback to pulling when the first get(...) fails.
        mock_docker_client.images.pull.assert_called_once_with("my-container", "v1.0")

        repository = f"{_get_registry_url()}/lit-container/test-org/test-team/my-container"
        mock_docker_client.api.tag.assert_called_once_with("my-container", repository, "v1.0")
        mock_docker_client.api.push.assert_called_once_with(
            repository, stream=True, decode=True, auth_config={"username": "admin", "api_key": "grid"}
        )


def test_upload_container_teamspace_resolution_error(lit_container):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve:
        # Setup mock to raise an exception
        mock_resolve.side_effect = Exception("Invalid teamspace")

        # Verify that the correct exception is raised
        with pytest.raises(ValueError, match="Could not resolve teamspace: Invalid teamspace"):
            lit_container.upload_container(container="my-container", teamspace="invalid-team")


def test_upload_container_auth_retry_success(lit_container, mock_teamspace):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve, patch.object(
        lit_container._api, "_docker_client"
    ) as mock_docker_client, patch.object(lit_container._api, "authenticate") as mock_authenticate, patch(
        "time.sleep"
    ) as mock_sleep:
        mock_resolve.return_value = mock_teamspace
        mock_docker_client.images.get.return_value = MagicMock(id="my-container")
        mock_docker_client.api.tag.return_value = True

        mock_docker_client.api.push.side_effect = [
            [
                {"status": "Pushing"},
                {
                    "errorDetail": {
                        "message": "something something something tcp: dial tcp 192.168.65.1:3128: i/o timeout"
                    },
                    "error": "something something something tcp: dial tcp 192.168.65.1:3128: i/o timeout",
                },
            ],
            [
                {"status": "Pushing"},
                {
                    "errorDetail": {
                        "message": "something something something tcp: dial tcp 192.168.65.1:3128: i/o timeout"
                    },
                    "error": "something something something tcp: dial tcp 192.168.65.1:3128: i/o timeout",
                },
            ],
            [{"status": "Pushing"}, {"status": "Complete"}],
        ]

        lit_container.upload_container(container="my-container", teamspace="test-team", tag="v1.0")
        assert mock_docker_client.api.push.call_count == 3
        assert mock_authenticate.call_count == 2
        mock_authenticate.assert_called_with(reauth=True)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(2)


def test_upload_container_timeout_retry_success(lit_container, mock_teamspace):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve, patch.object(
        lit_container._api, "_docker_client"
    ) as mock_docker_client, patch.object(lit_container._api, "authenticate") as mock_authenticate, patch(
        "time.sleep"
    ) as mock_sleep:
        mock_resolve.return_value = mock_teamspace
        mock_docker_client.images.get.return_value = MagicMock(id="my-container")
        mock_docker_client.api.tag.return_value = True

        mock_docker_client.api.push.side_effect = [
            [{"error": "unauthorized"}],
            [{"status": "Pushing"}, {"status": "Complete"}],
        ]

        lit_container.upload_container(container="my-container", teamspace="test-team", tag="v1.0")
        assert mock_docker_client.api.push.call_count == 2
        mock_authenticate.assert_called_once_with(reauth=True)
        mock_sleep.assert_called_once_with(2)


def test_upload_container_auth_retry_max_attempts(lit_container, mock_teamspace):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve, patch.object(
        lit_container._api, "_docker_client"
    ) as mock_docker_client, patch.object(lit_container._api, "authenticate") as mock_authenticate, patch(
        "time.sleep"
    ) as mock_sleep:
        mock_resolve.return_value = mock_teamspace
        mock_docker_client.images.get.return_value = MagicMock(id="my-container")
        mock_docker_client.api.tag.return_value = True

        lit_container._api._docker_auth_config = {"username": "admin", "api_key": "grid"}

        mock_docker_client.api.push.side_effect = [
            [{"error": "unauthorized"}],
            [{"error": "unauthorized"}],
            [{"error": "unauthorized"}],
        ]

        with pytest.raises(DockerPushError, match="Max retries reached"):
            lit_container.upload_container(container="my-container", teamspace="test-team", tag="v1.0")

        assert mock_docker_client.api.push.call_count == 3
        repository = f"{_get_registry_url()}/lit-container/test-org/test-team/my-container"
        mock_docker_client.api.push.assert_called_with(
            repository, stream=True, decode=True, auth_config={"username": "admin", "api_key": "grid"}
        )
        assert mock_authenticate.call_count == 2
        mock_authenticate.assert_called_with(reauth=True)
        mock_sleep.assert_called_with(2)
        assert mock_sleep.call_count == 2


def test_upload_container_timeout_retry_max_attempts(lit_container, mock_teamspace):
    with patch("lightning_sdk.lit_container._resolve_teamspace") as mock_resolve, patch.object(
        lit_container._api, "_docker_client"
    ) as mock_docker_client, patch.object(lit_container._api, "authenticate") as mock_authenticate, patch(
        "time.sleep"
    ) as mock_sleep:
        mock_resolve.return_value = mock_teamspace
        mock_docker_client.images.get.return_value = MagicMock(id="my-container")
        mock_docker_client.api.tag.return_value = True

        mock_docker_client.api.push.side_effect = [
            [
                {"status": "Pushing"},
                {
                    "errorDetail": {
                        "message": "something something something proxyconnect \
                            tcp: dial tcp 192.168.65.1:3128: i/o timeout"
                    },
                    "error": "something something something proxyconnect tcp: dial tcp 192.168.65.1:3128: i/o timeout",
                },
            ],
            [
                {"status": "Pushing"},
                {
                    "errorDetail": {
                        "message": "something something something \
                            proxyconnect tcp: dial tcp 192.168.65.1:3128: i/o timeout"
                    },
                    "error": "something something something proxyconnect tcp: dial tcp 192.168.65.1:3128: i/o timeout",
                },
            ],
            [
                {"status": "Pushing"},
                {
                    "errorDetail": {
                        "message": "something something something tcp: dial tcp 192.168.65.1:3128: i/o timeout"
                    },
                    "error": "something something something tcp: dial tcp 192.168.65.1:3128: i/o timeout",
                },
            ],
        ]

        with pytest.raises(DockerPushError, match="Max retries reached"):
            lit_container.upload_container(container="my-container", teamspace="test-team", tag="v1.0")

        assert mock_docker_client.api.push.call_count == 3
        assert mock_authenticate.call_count == 2
        mock_authenticate.assert_called_with(reauth=True)
        mock_sleep.assert_called_with(2)
        assert mock_sleep.call_count == 2


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
        lit_container._api._docker_auth_config = {"username": "admin", "api_key": "grid"}
        mock_resolve.return_value = mock_teamspace

        lit_container.download_container(container="my-container", teamspace="test-team", tag="latest")
        repository = f"{_get_registry_url()}/lit-container/test-org/test-team/my-container"
        (
            mock_docker_client.images.pull.assert_called_once_with(
                repository, tag="latest", auth_config={"username": "admin", "api_key": "grid"}
            ),
            "Docker pull was not called",
        )


@patch("lightning_sdk.api.lit_container_api.docker")
@patch("lightning_sdk.api.lit_container_api.LightningClient")
def test_authenticate(mock_lightning_client, mock_docker):
    api = LitContainerApi()
    mock_lightning_client.auth_service_get_user.return_value = MagicMock(username="test-user", api_key="test-key")
    api.authenticate()
    mock_docker.from_env.assert_called(), "Docker client was not created"
    mock_docker.from_env().login.assert_called(), "Docker client was not created"
