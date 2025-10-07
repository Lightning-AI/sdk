from unittest.mock import MagicMock

import pytest

from lightning_sdk import base_studio as base_studio_module
from lightning_sdk.api import base_studio_api as base_studio_api_module
from lightning_sdk.lightning_cloud.openapi.models import (
    V1CloudSpaceEnvironmentTemplate,
    V1ListCloudSpaceEnvironmentTemplatesResponse,
)


def test_base_studio_update(monkeypatch):
    resolve_user_mock = MagicMock()
    monkeypatch.setattr(base_studio_module, "_resolve_user", resolve_user_mock)

    mock_org = MagicMock()
    mock_org.name = "org"
    monkeypatch.setattr(base_studio_module, "_resolve_org", mock_org)

    client = MagicMock()
    monkeypatch.setattr(base_studio_api_module, "LightningClient", MagicMock(return_value=client))

    client.cloud_space_environment_template_service_get_cloud_space_environment_template.return_value = (
        V1CloudSpaceEnvironmentTemplate(
            id="test-template-id",
            name="some-template",
            config=MagicMock(
                allowed_machines=["machine1", "machine2"],
                default_machine="machine1",
                environment_type=MagicMock(name="environment_type"),
                machine_image_version="latest",
                setup_script_text="setup_script",
            ),
        )
    )

    base_studio = base_studio_module.BaseStudio(name="test-template-id", org="org", user="user")
    base_studio.update(
        name="test_template-2",
    )

    client.cloud_space_environment_template_service_update_cloud_space_environment_template.assert_called()
    call_body = (
        client.cloud_space_environment_template_service_update_cloud_space_environment_template._mock_mock_calls[
            0
        ].kwargs["body"]
    )
    assert call_body.name == "test_template-2"
    assert call_body.allowed_machines == ["machine1", "machine2"]


@pytest.mark.parametrize("managed", [True, False])
def test_base_studio_list(monkeypatch, managed):
    resolve_user_mock = MagicMock()
    monkeypatch.setattr(base_studio_module, "_resolve_user", resolve_user_mock)

    mock_org = MagicMock()
    mock_org.id = "org-id"
    monkeypatch.setattr(base_studio_module, "_resolve_org", mock_org)

    client = MagicMock()
    monkeypatch.setattr(base_studio_api_module, "LightningClient", MagicMock(return_value=client))

    base_studio = base_studio_module.BaseStudio(org=mock_org, user="user")

    mock_get_all = MagicMock()
    mock_get_all.return_value = V1ListCloudSpaceEnvironmentTemplatesResponse(
        templates=[
            V1CloudSpaceEnvironmentTemplate(
                id="test-template-id",
                name="some-template",
                managed_id="lightning-managed",
                config=MagicMock(
                    allowed_machines=["machine1", "machine2"],
                    default_machine="machine1",
                    environment_type=MagicMock(name="environment_type"),
                    machine_image_version="latest",
                    setup_script_text="setup_script",
                ),
            )
        ]
    )
    base_studio._base_studio_api.get_all_base_studios = mock_get_all

    a = base_studio.list(managed=managed)

    assert mock_get_all.called
    assert mock_get_all.call_count == 1

    assert len(a) == 1
    assert a[0].id == "test-template-id"


@pytest.mark.parametrize(("include_disabled", "expected_count"), [(True, 3), (False, 2), (None, 2)])
def test_base_studio_list_with_disabled_templates(monkeypatch, include_disabled, expected_count):
    """Test that include_disabled parameter correctly filters disabled templates."""
    resolve_user_mock = MagicMock()
    monkeypatch.setattr(base_studio_module, "_resolve_user", resolve_user_mock)

    mock_org = MagicMock()
    mock_org.id = "org-id"
    monkeypatch.setattr(base_studio_module, "_resolve_org", mock_org)

    client = MagicMock()
    monkeypatch.setattr(base_studio_api_module, "LightningClient", MagicMock(return_value=client))

    base_studio = base_studio_module.BaseStudio(org=mock_org, user="user")

    mock_get_all = MagicMock()
    mock_get_all.return_value = V1ListCloudSpaceEnvironmentTemplatesResponse(
        templates=[
            V1CloudSpaceEnvironmentTemplate(
                id="enabled-template-1",
                name="enabled-template-1",
                managed_id="lightning-managed-1",
                disabled=False,
                config=MagicMock(),
            ),
            V1CloudSpaceEnvironmentTemplate(
                id="enabled-template-2",
                name="enabled-template-2",
                managed_id="lightning-managed-2",
                disabled=False,
                config=MagicMock(),
            ),
            V1CloudSpaceEnvironmentTemplate(
                id="disabled-template-1",
                name="disabled-template-1",
                managed_id="lightning-managed-3",
                disabled=True,
                config=MagicMock(),
            ),
        ]
    )
    base_studio._base_studio_api.get_all_base_studios = mock_get_all

    result = base_studio.list(include_disabled=include_disabled)

    assert len(result) == expected_count

    if include_disabled:
        # All templates should be returned
        assert result[0].id == "enabled-template-1"
        assert result[0].enabled is True
        assert result[1].id == "enabled-template-2"
        assert result[1].enabled is True
        assert result[2].id == "disabled-template-1"
        assert result[2].enabled is False
    else:
        # Only enabled templates should be returned
        assert result[0].id == "enabled-template-1"
        assert result[0].enabled is True
        assert result[1].id == "enabled-template-2"
        assert result[1].enabled is True
        assert all(template.enabled for template in result)


def test_base_studio_list_creator_managed_templates(monkeypatch):
    """Test that managed templates show '⚡ Lightning AI' as creator."""
    resolve_user_mock = MagicMock()
    monkeypatch.setattr(base_studio_module, "_resolve_user", resolve_user_mock)

    mock_org = MagicMock()
    mock_org.id = "org-id"
    monkeypatch.setattr(base_studio_module, "_resolve_org", mock_org)

    client = MagicMock()
    monkeypatch.setattr(base_studio_api_module, "LightningClient", MagicMock(return_value=client))

    base_studio = base_studio_module.BaseStudio(org=mock_org, user="user")

    mock_get_all = MagicMock()
    mock_get_all.return_value = V1ListCloudSpaceEnvironmentTemplatesResponse(
        templates=[
            V1CloudSpaceEnvironmentTemplate(
                id="managed-template-1",
                name="managed-template-1",
                managed_id="lightning-managed-1",
                disabled=False,
                config=MagicMock(),
            ),
            V1CloudSpaceEnvironmentTemplate(
                id="managed-template-2",
                name="managed-template-2",
                managed_id="lightning-managed-2",
                disabled=False,
                config=MagicMock(),
            ),
        ]
    )
    base_studio._base_studio_api.get_all_base_studios = mock_get_all

    result = base_studio.list(managed=True, include_disabled=False)

    assert len(result) == 2
    assert result[0].creator == "⚡ Lightning AI"
    assert result[1].creator == "⚡ Lightning AI"


def test_base_studio_list_creator_unmanaged_templates(monkeypatch):
    """Test that unmanaged templates show the username of the creator."""
    resolve_user_mock = MagicMock()
    monkeypatch.setattr(base_studio_module, "_resolve_user", resolve_user_mock)

    mock_org = MagicMock()
    mock_org.id = "org-id"
    monkeypatch.setattr(base_studio_module, "_resolve_org", mock_org)

    client = MagicMock()
    monkeypatch.setattr(base_studio_api_module, "LightningClient", MagicMock(return_value=client))

    mock_user_api = MagicMock()
    mock_user_1 = MagicMock()
    mock_user_1.username = "fake_user"
    mock_user_2 = MagicMock()
    mock_user_2.username = "other_user"

    def get_user_by_id_side_effect(user_id):
        if user_id == "user-123":
            return mock_user_1
        if user_id == "user-456":
            return mock_user_2
        return None

    mock_user_api._get_user_by_id.side_effect = get_user_by_id_side_effect
    monkeypatch.setattr(base_studio_module, "UserApi", MagicMock(return_value=mock_user_api))

    base_studio = base_studio_module.BaseStudio(org=mock_org, user="user")

    mock_get_all = MagicMock()
    mock_get_all.return_value = V1ListCloudSpaceEnvironmentTemplatesResponse(
        templates=[
            V1CloudSpaceEnvironmentTemplate(
                id="custom-template-1",
                name="custom-template-1",
                managed_id="",
                user_id="user-123",
                disabled=False,
                config=MagicMock(),
            ),
            V1CloudSpaceEnvironmentTemplate(
                id="custom-template-2",
                name="custom-template-2",
                managed_id=None,
                user_id="user-456",
                disabled=False,
                config=MagicMock(),
            ),
        ]
    )
    base_studio._base_studio_api.get_all_base_studios = mock_get_all

    result = base_studio.list(managed=False, include_disabled=False)

    assert len(result) == 2
    assert result[0].creator == "fake_user"
    assert result[1].creator == "other_user"


def test_base_studio_list_creator_mixed_templates(monkeypatch):
    """Test that mixed managed and unmanaged templates show correct creators."""
    resolve_user_mock = MagicMock()
    monkeypatch.setattr(base_studio_module, "_resolve_user", resolve_user_mock)

    mock_org = MagicMock()
    mock_org.id = "org-id"
    monkeypatch.setattr(base_studio_module, "_resolve_org", mock_org)

    client = MagicMock()
    monkeypatch.setattr(base_studio_api_module, "LightningClient", MagicMock(return_value=client))

    mock_user_api = MagicMock()
    mock_user = MagicMock()
    mock_user.username = "custom_user"
    mock_user_api._get_user_by_id.return_value = mock_user
    monkeypatch.setattr(base_studio_module, "UserApi", MagicMock(return_value=mock_user_api))

    base_studio = base_studio_module.BaseStudio(org=mock_org, user="user")

    mock_get_all = MagicMock()
    mock_get_all.return_value = V1ListCloudSpaceEnvironmentTemplatesResponse(
        templates=[
            V1CloudSpaceEnvironmentTemplate(
                id="managed-template",
                name="managed-template",
                managed_id="lightning-managed",
                disabled=False,
                config=MagicMock(),
            ),
            V1CloudSpaceEnvironmentTemplate(
                id="custom-template",
                name="custom-template",
                managed_id="",
                user_id="user-789",
                disabled=False,
                config=MagicMock(),
            ),
        ]
    )
    base_studio._base_studio_api.get_all_base_studios = mock_get_all

    result = base_studio.list(include_disabled=False)

    assert len(result) == 2
    assert result[0].creator == "⚡ Lightning AI"
    assert result[1].creator == "custom_user"
