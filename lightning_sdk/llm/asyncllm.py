import os
from typing import AsyncGenerator, Dict, List, Optional, Union

from lightning_sdk.llm.llm import LLM


class AsyncLLM(LLM):
    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_completion_tokens: Optional[int] = 500,
        images: Optional[Union[List[str], str]] = None,
        conversation: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        stream: bool = False,
        upload_local_images: bool = False,
    ) -> Union[str, AsyncGenerator[str, None]]:
        if conversation and conversation not in self._conversations:
            self._get_conversations()

        if images:
            if isinstance(images, str):
                images = [images]
            for image in images:
                if not isinstance(image, str):
                    raise NotImplementedError(f"Image type {type(image)} are not supported yet.")
                if not image.startswith("http") and upload_local_images:
                    self._teamspace.upload_file(file_path=image, remote_path=f"images/{os.path.basename(image)}")

        conversation_id = self._conversations.get(conversation) if conversation else None
        output = await self._llm_api.async_start_conversation(
            prompt=prompt,
            system_prompt=system_prompt,
            max_completion_tokens=max_completion_tokens,
            images=images,
            assistant_id=self._model.id,
            conversation_id=conversation_id,
            billing_project_id=self._teamspace.id,
            metadata=metadata,
            name=conversation,
            stream=stream,
        )
        if not stream:
            if conversation and not conversation_id:
                self._conversations[conversation] = output.conversation_id
            return output.choices[0].delta.content
        return self._stream_chat_response(output, conversation=conversation)
