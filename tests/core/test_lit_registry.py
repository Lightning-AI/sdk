from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.api.lit_registry_api import LitRegistryApi
from lightning_sdk.lit_registry import LitRegistry


@pytest.fixture()
def mock_teamspace():
    teamspace = MagicMock()
    teamspace.id = "test-project-id"
    return teamspace


@pytest.fixture()
def mock_api_list_containers():
    repo = MagicMock()
    repo.name = "test-docker-image"
    repo.id = "test-image-id"
    repo.creation_time = datetime(2024, 1, 1, 12, 0, 0)
    return repo


def test_list_containers(mock_teamspace, mock_api_list_containers):
    with patch("lightning_sdk.lit_registry._resolve_teamspace") as mock_resolve_teamspace:
        mock_resolve_teamspace.return_value = mock_teamspace

        registry = LitRegistry()
        registry._api = MagicMock(spec=LitRegistryApi)
        registry._api.list_containers.return_value = [mock_api_list_containers]

        result = registry.list_containers(teamspace="test-teamspace")

        mock_resolve_teamspace.assert_called_once_with(teamspace="test-teamspace", org=None, user=None)
        registry._api.list_containers.assert_called_once_with("test-project-id")

        expected_result = [
            {"REPOSITORY": "test-docker-image", "IMAGE ID": "test-image-id", "CREATED": "2024-01-01 12:00:00"}
        ]
        assert result == expected_result


def test_list_containers_with_org(mock_teamspace, mock_api_list_containers):
    with patch("lightning_sdk.lit_registry._resolve_teamspace") as mock_resolve_teamspace:
        mock_resolve_teamspace.return_value = mock_teamspace

        registry = LitRegistry()
        registry._api = MagicMock(spec=LitRegistryApi)
        registry._api.list_containers.return_value = [mock_api_list_containers]

        result = registry.list_containers(teamspace="test-teamspace", org="test-org")

        mock_resolve_teamspace.assert_called_once_with(teamspace="test-teamspace", org="test-org", user=None)
        registry._api.list_containers.assert_called_once_with("test-project-id")

        expected_result = [
            {"REPOSITORY": "test-docker-image", "IMAGE ID": "test-image-id", "CREATED": "2024-01-01 12:00:00"}
        ]
        assert result == expected_result
