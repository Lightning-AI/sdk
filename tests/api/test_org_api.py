import pytest
from lightning_cloud.openapi import V1Organization
from lightning_sdk.api.org_api import OrgApi

def test_org_api(internal_org_api_mocker):
    org_api = OrgApi()
    
    org = org_api.get_org("org-abc")
    assert isinstance(org, V1Organization)


def test_org_api_valueerror(internal_org_api_mocker):

    org_api = OrgApi()


    with pytest.raises(ValueError, match="Org xyz does not exist"):
        org_api.get_org("xyz")
