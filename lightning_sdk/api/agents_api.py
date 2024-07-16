from typing import List, Optional

from lightning_sdk.lightning_cloud.openapi import (
    AgentsIdBody,
    EndpointsIdBody,
    V1Assistant,
    V1Endpoint,
    V1PromptSuggestion,
    V1UpstreamOpenAI,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class AgentApi:
    """Internal API client for handling Agents-related HTTP requests."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def get_agent(self, agent_id: str) -> V1Assistant:
        """Retrieve the agent by its ID."""
        try:
            return self._client.assistants_service_get_assistant(agent_id)
        except ValueError as e:
            raise ValueError(f"Agent {agent_id} does not exist") from e

    def delete_agent(self, agent_id: str, teamspace_id: str) -> None:
        """Delete the agent by its ID."""
        self._client.assistants_service_delete_assistant(id=agent_id, project_id=teamspace_id)

    def _get_agent_endpoint(self, endpoint_id: str, teampsace_id: str) -> V1Endpoint:
        return self._client.endpoint_service_get_endpoint(project_id=teampsace_id, ref=endpoint_id)

    def update_agent(
        self,
        agent_id: str,
        teamspace_id: str,
        name: Optional[str] = None,
        model: Optional[str] = None,
        description: Optional[str] = None,
        prompt_template: Optional[str] = None,
        prompt_suggestions: Optional[List[str]] = None,
        knowledge: Optional[str] = None,
        publish_status: Optional[str] = None,
        file_uploads_enabled: Optional[bool] = None,
    ) -> V1Assistant:
        """Update the agent with provided details."""
        agent = self.get_agent(agent_id)
        body = AgentsIdBody(
            cloudspace_id=agent.cloudspace_id,
            cluster_id=agent.cluster_id,
            description=agent.description,
            endpoint_id=agent.endpoint_id,
            knowledge=agent.knowledge,
            model=agent.model,
            name=agent.name,
            org_id=agent.org_id,
            prompt_suggestions=agent.prompt_suggestions,
            prompt_template=agent.prompt_template,
            user_id=agent.user_id,
            publish_status=agent.publish_status,
            file_uploads_enabled=agent.file_uploads_enabled,
        )

        if name is not None:
            body.name = name
        if model is not None:
            body.model = model
        if description is not None:
            body.description = description
        if prompt_template is not None:
            body.prompt_template = prompt_template
        if prompt_suggestions is not None:
            formatted_prompt_suggestions = [V1PromptSuggestion(content=suggestion) for suggestion in prompt_suggestions]
            body.prompt_suggestions = formatted_prompt_suggestions
        if knowledge is not None:
            body.knowledge = knowledge
        if publish_status is not None:
            body.publish_status = publish_status
        if file_uploads_enabled is not None:
            body.file_uploads_enabled = file_uploads_enabled

        return self._client.assistants_service_update_assistant(
            id=agent_id,
            project_id=teamspace_id,
            body=body,
        )

    def update_agent_endpoint(
        self, teamspace_id: str, endpoint_id: str, base_url: Optional[str] = None, api_key: Optional[str] = None
    ) -> V1Endpoint:
        """Update the agent endpoint with provided details."""
        endpoint = self._get_agent_endpoint(teampsace_id=teamspace_id, endpoint_id=endpoint_id)

        body = EndpointsIdBody(
            name=endpoint.name,
            openai=V1UpstreamOpenAI(api_key=endpoint.openai.api_key, base_url=endpoint.openai.base_url),
        )

        if base_url is not None:
            body.openai.base_url = base_url
        if api_key is not None:
            body.openai.api_key = api_key

        return self._client.endpoint_service_update_endpoint(
            project_id=teamspace_id, id=endpoint_id, body=body, async_req=True
        )
