from unittest import mock

import pytest
from lightning_cloud.openapi import V1ListOrganizationsResponse, V1Organization


@mock.patch("lightning.app.utilities.network.LightningClient")
def test_org_api(patch):
    from lightning_sdk.api.org_api import OrgApi

    org_api = OrgApi()

    # mock internal api response
    org_api._client.api_client.call_api.return_value = V1ListOrganizationsResponse(
        [V1Organization(display_name="abc", name="abc"), V1Organization(display_name="def", name="def")]
    )

    org = org_api.get_org("abc")
    assert isinstance(org, V1Organization)


@mock.patch("lightning.app.utilities.network.LightningClient")
def test_org_api_valueerror(patch):
    from lightning_sdk.api.org_api import OrgApi

    org_api = OrgApi()

    # mock internal api response
    org_api._client.api_client.call_api.return_value = V1ListOrganizationsResponse(
        [V1Organization(display_name="def", name="def")]
    )

    with pytest.raises(ValueError, match="Org abc does not exist"):
        org_api.get_org("abc")
