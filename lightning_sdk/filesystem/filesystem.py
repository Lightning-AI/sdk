import logging

from lightning_sdk.api.filesystem_api import FilesystemApi
from lightning_sdk.cli.utils.filesystem import resolve_teamspace
from lightning_sdk.utils.filesystem import parse_lit_url
from lightning_sdk.utils.logging import TrackCallsMeta

logger = logging.getLogger(__name__)


class Filesystem(metaclass=TrackCallsMeta):
    """Abstraction for interacting with the teamspace drive."""

    def __init__(
        self,
    ) -> None:
        self._filesystem_api = FilesystemApi()

    def copy(
        self,
        source: str,
        destination: str,
        progress_bar: bool = True,
    ) -> None:
        source_is_lit = source.startswith("lit://")
        dest_is_lit = destination.startswith("lit://")

        if source_is_lit and dest_is_lit:
            raise ValueError("Cannot copy between two remote URLs. One path must be local.")

        if not source_is_lit and not dest_is_lit:
            raise ValueError("At least one path must be a lit://")

        path_result = parse_lit_url(source if source_is_lit else destination)

        selected_teamspace = resolve_teamspace(path_result["teamspace"], path_result["owner"])
        if source_is_lit:
            # download
            self._filesystem_api.download_file(
                path_result["destination"], destination, selected_teamspace.id, progress_bar
            )
        else:
            # upload
            raise NotImplementedError("Filesystem upload is not implemented.")
