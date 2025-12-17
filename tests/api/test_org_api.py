from unittest import mock

import pytest

from lightning_sdk.api.org_api import OrgApi
from lightning_sdk.lightning_cloud.openapi import V1Organization


def test_org_api(internal_get_org_api_mocker):
    org_api = OrgApi()

    org = org_api.get_org("org-abc")
    assert isinstance(org, V1Organization)


def test_org_api_valueerror(internal_get_org_api_mocker):
    org_api = OrgApi()

    with pytest.raises(ValueError, match="Org xyz does not exist"):
        org_api.get_org("xyz")


@mock.patch("lightning_sdk.api.org_api.LightningClient")
def test_create_teamspace(mock_client):
    org_api = OrgApi()

    org_api.create_teamspace("my-teamspace", "org-123")

    mock_client().projects_service_create_project.assert_called_once()
    call_args = mock_client().projects_service_create_project.call_args
    assert call_args[1]["body"].name == "my-teamspace"
    assert call_args[1]["body"].display_name == "my-teamspace"
    assert call_args[1]["body"].organization_id == "org-123"
