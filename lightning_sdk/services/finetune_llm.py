from typing import Literal

from lightning_sdk.services.file_endpoint import Client


class LLMFinetune(Client):
    """The LLM Finetune is the client to the LLM Finetune Service Studio.

    Learn more: https://lightning.ai/lightning-ai/studios/llm-finetune-service~01h5rahq6gbhw5m4bzyws0at5h.

    """

    def __init__(self, teamspace: str) -> None:
        super().__init__(name="lightning-al/llm-finetunes", teamspace=teamspace)

    def run(
        self,
        data_path: str,
        model: Literal["llama-2-7b", "tiny-llama"] = "tiny-llama",
        mode: Literal["lora", "full"] = "lora",
        epochs: int = 3,
        learning_rate: float = 0.0002,
        micro_batch_size: int = 2,
        global_batch_size: int = 8,
    ) -> None:
        """The run method executes the LLM Finetune Service."""
        super().run(
            data_path=data_path,
            model=model,
            mode=mode,
            epochs=epochs,
            learning_rate=learning_rate,
            micro_batch_size=micro_batch_size,
            global_batch_size=global_batch_size,
        )
