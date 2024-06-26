from typing import List, Optional

from lightning_sdk.api.agents_api import AgentApi


class Agent:
    def __init__(self, agent_id: str) -> None:
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
        """Update the agent and its endpoint."""
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
        self._agent_api.delete_agent(agent_id=self.id, teamspace_id=self._agent.project_id)
