from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.api.lit_container_api import LCRAuthFailedError, LitContainerApi, retry_on_lcr_auth_failure


def test_retry_on_lcr_auth_failure_generator():
    items = [1, 2, 3, 4, 5]

    class Test:
        @retry_on_lcr_auth_failure
        def _gen_fn(self):
            while items:
                i = items.pop(0)
                yield i
                if i == 3:
                    raise LCRAuthFailedError()

    api = Test()
    api.authenticate = MagicMock(return_value=True)
    assert list(api._gen_fn()) == [1, 2, 3, 4, 5]
    api.authenticate.assert_called_once()


def test_retry_on_lcr_auth_failure():
    items = [1, 2]

    class Test:
        @retry_on_lcr_auth_failure
        def _gen_fn(self):
            i = items.pop(0)
            if i == 1:
                raise LCRAuthFailedError()
            return i

    api = Test()
    api.authenticate = MagicMock(return_value=True)
    assert api._gen_fn() == 2
    api.authenticate.assert_called_once()


@patch("lightning_sdk.api.lit_container_api.LightningClient")
@patch("lightning_sdk.api.lit_container_api.docker.from_env")
def test_delete_container_by_digest(_mock_docker_from_env, _mock_lightning_client):
    api = LitContainerApi()
    api._client = MagicMock()

    api.delete_container_by_digest("proj-123", "nginx", "sha256:abc123")

    api._client.lit_registry_service_delete_lit_registry_repository_image_artifact_version_by_digest.assert_called_once_with(
        "proj-123", "nginx", "sha256:abc123"
    )


@patch("lightning_sdk.api.lit_container_api.LightningClient")
@patch("lightning_sdk.api.lit_container_api.docker.from_env")
def test_delete_container_by_digest_raises_on_error(_mock_docker_from_env, _mock_lightning_client):
    api = LitContainerApi()
    api._client = MagicMock()
    api._client.lit_registry_service_delete_lit_registry_repository_image_artifact_version_by_digest.side_effect = (
        Exception("not found")
    )

    with pytest.raises(
        ValueError, match="Could not delete digest sha256:abc123 of container nginx from project proj-123"
    ):
        api.delete_container_by_digest("proj-123", "nginx", "sha256:abc123")
