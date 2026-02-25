import logging
import os
from typing import Generator, List, Tuple

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

    def listdir(self, uri: str) -> List[str]:
        path_result = parse_lit_url(uri)
        selected_teamspace = resolve_teamspace(path_result["teamspace"], path_result["owner"])
        output = self._filesystem_api.list_files(
            teamspace_id=selected_teamspace.id, path=path_result["destination"], recursive=False
        )
        return [os.path.basename(item["path"]) for item in output]

    def walk(self, url: str) -> Generator[Tuple[str, List[str], List[str]], None, None]:
        path_result = parse_lit_url(url)
        selected_teamspace = resolve_teamspace(path_result["teamspace"], path_result["owner"])
        output = self._filesystem_api.list_files(
            teamspace_id=selected_teamspace.id, path=path_result["destination"], recursive=True
        )

        dirs: dict[str, list[str]] = {}
        files: dict[str, list[str]] = {}

        for entry in output:
            parent = os.path.dirname(entry["path"])
            name = os.path.basename(entry["path"])
            files.setdefault(parent, []).append(name)

            parts = parent.split("/")
            for i in range(1, len(parts) + 1):
                dirpath = "/".join(parts[:i])
                dirs.setdefault(dirpath, [])
                if i < len(parts):
                    child = parts[i]
                    if child not in dirs[dirpath]:
                        dirs[dirpath].append(child)

        for dirpath in sorted(dirs):
            yield dirpath, dirs[dirpath], files.get(dirpath, [])

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
