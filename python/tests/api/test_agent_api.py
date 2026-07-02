from unittest import mock

from lightning_sdk.api.agents_api import AgentApi


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
def test_get_agent(_mock_auth, internal_agents_api_get_agent_mocker):
    agent_api = AgentApi()
    agent = agent_api.get_agent("ag-abc")
    assert agent.id == "ag-abc"
    assert agent.name == "ag-abc"


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
def test_delete_agent(_mock_auth, internal_agents_api_delete_agent_mocker):
    agent_api = AgentApi()
    agent_api.delete_agent("ag-abc", "ts-abc")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
def test_update_agent(_mock_auth, internal_agents_api_update_agent_mocker, internal_agents_api_get_agent_mocker):
    agent_api = AgentApi()
    new_agent = agent_api.update_agent("ag-abc", "ts-abc", name="test-sdk-1")
    assert new_agent.name == "test-sdk-1"


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
def test_update_endpoint(
    _mock_auth, internal_agents_api_update_agent_endpoint_mocker, internal_agents_api_get_agent_endpoint_mocker
):
    agent_api = AgentApi()
    new_endpoint = agent_api.update_agent_endpoint("ts-abc", "ag-abc", base_url="test-sdk-1", api_key="test-sdk-1")
    assert new_endpoint.openai.base_url == "test-sdk-1"
    assert new_endpoint.openai.api_key == "test-sdk-1"


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
def test_get_agent_endpoint(_mock_auth, internal_agents_api_get_agent_endpoint_mocker):
    agent_api = AgentApi()
    endpoint = agent_api._get_agent_endpoint("ep-abc", "ts-abc")
    assert endpoint.id == "ep-abc"
    assert endpoint.project_id == "ts-abc"
