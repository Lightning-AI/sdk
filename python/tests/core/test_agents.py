from unittest import mock

from lightning_sdk.agents import Agent
from lightning_sdk.lightning_cloud.openapi import V1Assistant


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_agent_init(internal_agents_api_get_agent_mocker):
    agent = Agent("ag-abc")
    assert isinstance(agent._agent, V1Assistant)
    assert agent._agent.name == "ag-abc"


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_agent_delete(internal_agents_api_delete_agent_mocker, internal_agents_api_get_agent_mocker):
    agent = Agent("ag-abc")
    agent.delete()


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_agent_update(
    internal_agents_api_update_agent_mocker,
    internal_agents_api_get_agent_mocker,
    internal_agents_api_update_agent_endpoint_mocker,
    internal_agents_api_get_agent_endpoint_mocker,
):
    agent = Agent("ag-abc")
    agent.update(
        name="new-name",
    )
    assert agent._agent.name == "new-name"
