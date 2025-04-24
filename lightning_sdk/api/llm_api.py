from typing import List, Optional

from lightning_sdk.lightning_cloud.openapi.models.v1_conversation_response_chunk import V1ConversationResponseChunk
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class LLMApi:
    def __init__(self) -> None:
        self._client = LightningClient(retry=False, max_tries=0)

    def list_models(self) -> List[str]:
        result = self._client.assistants_service_list_assistant_managed_endpoints()
        return result.endpoints

    def get_public_models(self) -> List[str]:
        result = self._client.assistants_service_list_assistants(published=True)
        return result.assistants

    def start_conversation(
        self, prompt: str, system_prompt: Optional[str], assistant_id: str
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
        }
        result = self._client.assistants_service_start_conversation(body, assistant_id)
        return result.result
