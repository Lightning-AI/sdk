from unittest import mock

from lightning_sdk.lightning_cloud.openapi import V1CloudSpace, V1ListCloudSpacesResponse
from lightning_sdk.studio import Studio


def list_cloudspaces_side_effect(existing_studios):
    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    return _list_cloudspaces_side_effect


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_studio_rename():
    """Test that Studio.rename calls StudioApi._update_cloudspace and _update_studio_reference correctly."""
    # Setup
    mock_studio = V1CloudSpace(id="st-abc", name="st-abc", display_name="st-abc", cluster_id="c-abc")
    studio = Studio.__new__(Studio)
    studio._studio = mock_studio
    studio._studio_api = mock.MagicMock()
    studio._teamspace = mock.MagicMock()
    studio._teamspace.id = "ts-abc"
    studio._update_studio_reference = mock.MagicMock()

    studio.rename("st-xyz")
    studio._studio_api._update_cloudspace.assert_called_once_with(mock_studio, "ts-abc", "display_name", "st-xyz")
    studio._update_studio_reference.assert_called_once()

    # Reset
    studio._studio_api._update_cloudspace.reset_mock()
    studio._update_studio_reference.reset_mock()

    studio.rename("st-abc")
    studio._studio_api._update_cloudspace.assert_not_called()
    studio._update_studio_reference.assert_not_called()
