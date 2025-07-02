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
