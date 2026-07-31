from unittest import mock

import pytest

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
def test_studio_env_property():
    """Test that Studio.env property calls StudioApi.get_env correctly."""
    from lightning_sdk.lightning_cloud.openapi import V1EnvVar

    # Create a simple mock studio object
    mock_studio = V1CloudSpace(
        id="st-abc",
        name="st-abc",
        cluster_id="c-abc",
        env=[V1EnvVar(name="TEST_VAR", value="test_value"), V1EnvVar(name="ANOTHER_VAR", value="another_value")],
    )

    # Mock the Studio object and directly test the env property
    studio = Studio.__new__(Studio)  # Create without __init__
    studio._studio = mock_studio
    studio._studio_api = mock.MagicMock()
    studio._studio_api.get_env.return_value = {"TEST_VAR": "test_value", "ANOTHER_VAR": "another_value"}
    studio._update_studio_reference = mock.MagicMock()

    # Test the env property
    env_vars = studio.env

    assert env_vars == {"TEST_VAR": "test_value", "ANOTHER_VAR": "another_value"}
    studio._update_studio_reference.assert_called_once()
    studio._studio_api.get_env.assert_called_once_with(mock_studio)


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_studio_set_env_partial_true():
    """Test that Studio.set_env calls StudioApi.set_env correctly with partial=True."""
    mock_studio = V1CloudSpace(id="st-abc", name="st-abc", cluster_id="c-abc")

    # Mock the Studio object and directly test the set_env method
    studio = Studio.__new__(Studio)  # Create without __init__
    studio._studio = mock_studio
    studio._studio_api = mock.MagicMock()
    studio._teamspace = mock.MagicMock()
    studio._teamspace.id = "ts-abc"

    new_env = {"NEW_VAR": "new_value", "UPDATED_VAR": "updated_value"}
    studio.set_env(new_env, partial=True)

    studio._studio_api.set_env.assert_called_once_with(mock_studio, "ts-abc", new_env, partial=True)


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_studio_set_env_partial_false():
    """Test that Studio.set_env calls StudioApi.set_env correctly with partial=False."""
    mock_studio = V1CloudSpace(id="st-abc", name="st-abc", cluster_id="c-abc")

    # Mock the Studio object and directly test the set_env method
    studio = Studio.__new__(Studio)  # Create without __init__
    studio._studio = mock_studio
    studio._studio_api = mock.MagicMock()
    studio._teamspace = mock.MagicMock()
    studio._teamspace.id = "ts-abc"

    new_env = {"ONLY_VAR": "only_value"}
    studio.set_env(new_env, partial=False)

    studio._studio_api.set_env.assert_called_once_with(mock_studio, "ts-abc", new_env, partial=False)


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_studio_set_env_validates_names_and_accepts_empty_values():
    studio = Studio.__new__(Studio)
    studio._studio = V1CloudSpace(id="st-abc", name="st-abc", cluster_id="c-abc")
    studio._studio_api = mock.MagicMock()
    studio._teamspace = mock.MagicMock(id="ts-abc")

    new_env = {"_NAME": "", "NAME_2": "value"}
    studio.set_env(new_env)

    studio._studio_api.set_env.assert_called_once_with(studio._studio, "ts-abc", new_env, partial=True)

    for invalid_name in ("", "2_NAME", "INVALID-NAME"):
        with pytest.raises(ValueError, match="Environment variable names must start"):
            studio.set_env({invalid_name: "value"})

    assert studio._studio_api.set_env.call_count == 1


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_studio_delete_env_preserves_unrelated_variables():
    studio = Studio.__new__(Studio)
    studio._studio = V1CloudSpace(id="st-abc", name="st-abc", cluster_id="c-abc")
    studio._studio_api = mock.MagicMock()
    studio._teamspace = mock.MagicMock(id="ts-abc")

    with mock.patch.object(
        Studio, "env", new_callable=mock.PropertyMock, return_value={"KEEP": "yes", "OLD": "remove"}
    ):
        studio.delete_env("OLD")

    studio._studio_api.set_env.assert_called_once_with(studio._studio, "ts-abc", {"KEEP": "yes"}, partial=False)


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_studio_delete_env_handles_final_missing_and_invalid_names():
    studio = Studio.__new__(Studio)
    studio._studio = V1CloudSpace(id="st-abc", name="st-abc", cluster_id="c-abc")
    studio._studio_api = mock.MagicMock()
    studio._teamspace = mock.MagicMock(id="ts-abc")

    with mock.patch.object(Studio, "env", new_callable=mock.PropertyMock, return_value={"ONLY": "value"}):
        studio.delete_env("ONLY")
    studio._studio_api.set_env.assert_called_once_with(studio._studio, "ts-abc", {}, partial=False)

    studio._studio_api.reset_mock()
    with mock.patch.object(Studio, "env", new_callable=mock.PropertyMock, return_value={}), pytest.raises(
        ValueError, match="Studio environment variable 'MISSING' was not found"
    ):
        studio.delete_env("MISSING")
    with pytest.raises(ValueError, match="Environment variable names must start"):
        studio.delete_env("INVALID-NAME")
    studio._studio_api.set_env.assert_not_called()
