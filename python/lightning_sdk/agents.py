from typing import List, Optional

from lightning_sdk.api.agents_api import AgentApi
from lightning_sdk.utils.logging import TrackCallsMeta


class Agent(metaclass=TrackCallsMeta):
    """Represents a Lightning AI Agent.

    Agents expose an AI assistant endpoint backed by a custom model and prompt configuration.
    Use :meth:`~lightning_sdk.Teamspace.create_agent` to create a new agent, then use this
    class to update or delete it.
    """

    def __init__(self, agent_id: str) -> None:
        """Fetch an existing agent by its ID.

        Args:
            agent_id: The unique identifier of the agent to fetch.

        Raises:
            ValueError: If no agent with the given ID exists.
        """
        self.id = agent_id
        self._agent_api = AgentApi()

        try:
            self._agent = self._agent_api.get_agent(agent_id)
        except ValueError as e:
            raise ValueError(f"Agent {agent_id}") from e

    def update(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        name: Optional[str] = None,
        model: Optional[str] = None,
        description: Optional[str] = None,
        prompt_template: Optional[str] = None,
        prompt_suggestions: Optional[List[str]] = None,
        knowledge: Optional[str] = None,
        publish_status: Optional[str] = None,
    ) -> None:
        """Update the agent configuration and its backing endpoint.

        All parameters are optional; only the provided values are updated.

        Args:
            base_url: New base URL for the model endpoint. Defaults to None.
            api_key: New API key for authenticating with the endpoint. Defaults to None.
            name: New display name for the agent. Defaults to None.
            model: New model identifier to use. Defaults to None.
            description: New human-readable description for the agent. Defaults to None.
            prompt_template: New system prompt template. Defaults to None.
            prompt_suggestions: New list of suggested user prompts shown in the UI. Defaults to None.
            knowledge: New knowledge-base content or reference for the agent. Defaults to None.
            publish_status: New publish status (e.g. ``"published"`` or ``"draft"``). Defaults to None.
        """
        self._agent_api.update_agent_endpoint(
            teamspace_id=self._agent.project_id, endpoint_id=self._agent.endpoint_id, base_url=base_url, api_key=api_key
        )
        agent = self._agent_api.update_agent(
            agent_id=self.id,
            teamspace_id=self._agent.project_id,
            name=name,
            model=model,
            description=description,
            prompt_template=prompt_template,
            prompt_suggestions=prompt_suggestions,
            knowledge=knowledge,
            publish_status=publish_status,
        )
        self._agent = agent

    def delete(self) -> None:
        """Permanently delete the agent and its associated endpoint."""
        self._agent_api.delete_agent(agent_id=self.id, teamspace_id=self._agent.project_id)
