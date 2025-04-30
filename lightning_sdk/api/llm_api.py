from typing import List, Optional

from lightning_sdk.lightning_cloud.openapi.models.v1_conversation_response_chunk import V1ConversationResponseChunk
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class LLMApi:
    def __init__(self) -> None:
        self._client = LightningClient(retry=False, max_tries=0)

    def get_public_models(self) -> List[str]:
        result = self._client.assistants_service_list_assistants(published=True)
        return result.assistants

    def get_org_models(self, org_id: str) -> List[str]:
        result = self._client.assistants_service_list_assistants(org_id=org_id)
        return result.assistants

    def get_user_models(self, user_id: str) -> List[str]:
        result = self._client.assistants_service_list_assistants(user_id=user_id)
        return result.assistants

    def start_conversation(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_completion_tokens: Optional[int],
        assistant_id: str,
        conversation_id: Optional[str],
    ) -> V1ConversationResponseChunk:
        body = {
            "message": {
                "author": {"role": "user"},
                "content": [
                    {
                        "contentType": "text",
                        "parts": [prompt],
                    }
                ],
            },
            "max_completion_tokens": max_completion_tokens,
        }
        if conversation_id:
            body["conversation_id"] = conversation_id
        result = self._client.assistants_service_start_conversation(body, assistant_id)
        return result.result
