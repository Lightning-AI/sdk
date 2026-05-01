from typing import Literal

from lightning_sdk.services.file_endpoint import Client


class LLMFinetune(Client):
    """The LLM Finetune is the client to the LLM Finetune Service Studio.

    Learn more: https://lightning.ai/lightning-ai/studios/llm-finetune-service~01h5rahq6gbhw5m4bzyws0at5h.

    """

    def __init__(self, teamspace: str) -> None:
        """Connect to the LLM Finetune Service in the given teamspace.

        Args:
            teamspace: The name of the teamspace that hosts the LLM Finetune Service.
        """
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
        """Fine-tune a large language model using the LLM Finetune Service.

        Args:
            data_path: Path to the training data file.
            model: Base model to fine-tune. Defaults to ``"tiny-llama"``.
            mode: Fine-tuning mode — ``"lora"`` for LoRA or ``"full"`` for full fine-tuning.
                Defaults to ``"lora"``.
            epochs: Number of training epochs. Defaults to 3.
            learning_rate: Learning rate for training. Defaults to 0.0002.
            micro_batch_size: Micro-batch size per GPU. Defaults to 2.
            global_batch_size: Total batch size across all GPUs. Defaults to 8.
        """
        super().run(
            data_path=data_path,
            model=model,
            mode=mode,
            epochs=epochs,
            learning_rate=learning_rate,
            micro_batch_size=micro_batch_size,
            global_batch_size=global_batch_size,
        )
