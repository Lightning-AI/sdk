from fire import Fire
from lightning_utilities.core.imports import RequirementCache

from lightning_sdk.api.studio_api import _cloud_url
from lightning_sdk.cli.ai_hub import _AIHub
from lightning_sdk.cli.download import _Downloads
from lightning_sdk.cli.legacy import _LegacyLightningCLI
from lightning_sdk.cli.run import _Run
from lightning_sdk.cli.serve import _Docker, _LitServe
from lightning_sdk.cli.upload import _Uploads
from lightning_sdk.lightning_cloud.login import Auth

_LIGHTNING_AVAILABLE = RequirementCache("lightning")


class StudioCLI:
    """Command line interface (CLI) to interact with/manage Lightning AI Studios."""

    def __init__(self) -> None:
        self.download = _Downloads()
        self.upload = _Uploads()
        self.aihub = _AIHub()
        self.run = _Run(legacy_run=_LegacyLightningCLI() if _LIGHTNING_AVAILABLE else None)
        self.serve = _LitServe()
        self.dockerize = _Docker()

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


def main_cli() -> None:
    """CLI entrypoint."""
    Fire(StudioCLI(), name="lightning")


if __name__ == "__main__":
    main_cli()
