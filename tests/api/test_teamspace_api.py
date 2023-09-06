from unittest import mock

import pytest
from lightning_cloud.openapi import V1Project
from lightning_sdk.api.teamspace_api import TeamspaceApi

def test_get_teamspace(internal_teamspace_api_mocker):

    teamspace_api = TeamspaceApi()

    project = teamspace_api.get_teamspace("ts-abc", "org-def")
    assert isinstance(project, V1Project)


def test_get_teamspace_error(internal_teamspace_api_mocker):

    teamspace_api = TeamspaceApi()

    with pytest.raises(ValueError, match="Teamspace xyz does not exist"):
        teamspace_api.get_teamspace("xyz", "org-def")
