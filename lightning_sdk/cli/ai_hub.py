from typing import List, Optional

from lightning_sdk.ai_hub import AIHub
from lightning_sdk.cli.studios_menu import _StudiosMenu


class _AIHub(_StudiosMenu):
    """Interact with Lightning Studio - AI Hub."""

    def __init__(self) -> None:
        self._hub = AIHub()

    def list_apis(self, search: Optional[str] = None) -> List[dict]:
        """List API templates available in the AI Hub.

        Args:
          search: Search for API templates by name.
        """
        return self._hub.list_apis(search=search)
