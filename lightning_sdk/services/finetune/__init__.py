from typing import Literal

from lightning_sdk.services.file_endpoint import FileEndpoint


class LLMFinetune(FileEndpoint):
    """The LLM Finetune is the client to the LLM Finetune Service Studio.

    Learn more: https://lightning.ai/lightning-ai/studios/llm-finetune-service~01h5rahq6gbhw5m4bzyws0at5h.

    """

    def __init__(self) -> None:
        super().__init__(url="https://finetune-01hra53x9nzbhc774s2ecp7bcp.cloudspaces.litng.ai")

    def run(
        self,
        data_path: str,
        model: Literal["llama-2-7b", "tiny-llama"] = "tiny-llama",
        mode: Literal["lora", "full"] = "lora",
        epochs: int = 3,
        learning_rate: float = 0.0002,
        micro_batch_size: int = 2,
        global_batch_size: int = 8,
        output_dir: str = "results",
    ) -> None:
        """The run method executes the LLM Finetune Service."""
        args = {
            "model": str(model),
            "mode": str(mode),
            "epochs": str(epochs),
            "learning_rate": str(learning_rate),
            "micro_batch_size": str(micro_batch_size),
            "global_batch_size": str(global_batch_size),
        }
        files = {"data_path": data_path}
        super().run(args, files, output_dir)
