from fire import Fire

from lightning_sdk.api.studio_api import _cloud_url
from lightning_sdk.cli.upload import _Uploads
from lightning_sdk.lightning_cloud.login import Auth


class StudioCLI(_Uploads):
    """Command line interface (CLI) to interact with/manage Lightning AI Studios."""

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
    Fire(StudioCLI())
