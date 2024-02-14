import subprocess
import warnings
from typing import Any, Optional, Union

from fire import Fire
from lightning_utilities.core.imports import RequirementCache

from lightning_sdk.api.studio_api import _cloud_url
from lightning_sdk.cli.upload import _Uploads
from lightning_sdk.lightning_cloud.login import Auth

_LIGHTNING_AVAILABLE = RequirementCache("lightning")
_FABRIC_AVAILABLE = RequirementCache("lightning_fabric")


class StudioCLI(_Uploads):
    """Command line interface (CLI) to interact with/manage Lightning AI Studios."""

    def __init__(self) -> None:
        if _LIGHTNING_AVAILABLE or _FABRIC_AVAILABLE:
            self.run = _LegacyFabricCLI()

    def login(self) -> None:
        """Login to Lightning AI Studios."""
        auth = Auth()
        auth.clear()

        try:
            auth.authenticate()
        except ConnectionError:
            raise RuntimeError(f"Unable to connect to {_cloud_url()}. Please check your internet connection.") from None

    def logout(self) -> None:
        """Logout from Lightning AI Studios."""
        auth = Auth()
        auth.clear()


class _LegacyFabricCLI:
    """Legacy CLI for `fabric run model`."""

    def model(
        self,
        script: str,
        accelerator: Optional[str] = None,
        strategy: Optional[str] = None,
        devices: str = "1",
        num_nodes: int = 1,
        node_rank: int = 0,
        main_address: str = "127.0.0.1",
        main_port: int = 29400,
        precision: Optional[Union[int, str]] = None,
        *script_args: Any,
    ) -> None:
        """Legacy CLI for `fabric run model`.

        Args:
            script: The script containing the fabric definition to launch
            accelerator: The hardware accelerator to run on.
            strategy: Strategy for how to run across multiple devices.
            devices: Number of devices to run on (``int``), which devices to run on (``list`` or ``str``),
                or ``'auto'``. The value applies per node.
            num_nodes: Number of machines (nodes) for distributed execution.
            node_rank: The index of the machine (node) this command gets started on.
                Must be a number in the range 0, ..., num_nodes - 1.
            main_address: The hostname or IP address of the main machine (usually the one with node_rank = 0).
            main_port: The main port to connect to the main machine.
            precision: Double precision (``64-true`` or ``64``), full precision (``32-true`` or ``64``),
                half precision (``16-mixed`` or ``16``) or bfloat16 precision (``bf16-mixed`` or ``bf16``)
            script_args: Arguments passed to the script to execute

        """
        warnings.warn(
            "lightning run model is deprecated and will be removed in future versions."
            " Please call `fabric run model` instead.",
            DeprecationWarning,
        )

        args = []
        if accelerator is not None:
            args.extend(["--accelerator", accelerator])

        if strategy is not None:
            args.extend(["--strategy", strategy])

        args.extend(["--devices", devices])
        args.extend(["--num_nodes", num_nodes])
        args.extend(["--node_rank", node_rank])
        args.extend(["--main_address", main_address])
        args.extend(["--main_port", main_port])

        if precision is not None:
            args.extend(["--precision", precision])

        args.extend(list(script_args))
        subprocess.run(["fabric", "run", "model", script, *args])


def main_cli() -> None:
    """CLI entrypoint."""
    Fire(StudioCLI(), name="lightning")


if __name__ == "__main__":
    main_cli()
