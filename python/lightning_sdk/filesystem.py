import logging
import os
from typing import Generator, List, Tuple

from lightning_sdk.api import lightning_storage_upload as lightning_storage_upload_api
from lightning_sdk.api.filesystem_api import FilesystemApi
from lightning_sdk.cli.utils.filesystem import resolve_teamspace
from lightning_sdk.utils.filesystem import parse_lit_url
from lightning_sdk.utils.logging import TrackCallsMeta

logger = logging.getLogger(__name__)

__all__ = [
    "Filesystem",
]


def _is_lightning_storage_destination(path: str) -> bool:
    normalized = path.strip("/")
    return normalized == "lightning_storage" or normalized.startswith("lightning_storage/")


class Filesystem(metaclass=TrackCallsMeta):
    """Abstraction for interacting with the teamspace drive."""

    def __init__(
        self,
    ) -> None:
        self._filesystem_api = FilesystemApi()

    def listdir(self, uri: str) -> List[str]:
        """List the immediate children of a remote directory.

        Args:
            uri: Remote path in ``lit://[owner/][teamspace/]destination`` format.

        Returns:
            List[str]: Basenames of the entries directly inside the given directory.
        """
        path_result = parse_lit_url(uri)
        selected_teamspace = resolve_teamspace(path_result["teamspace"], path_result["owner"])
        output = self._filesystem_api.list_files(
            teamspace_id=selected_teamspace.id, path=path_result["destination"], recursive=False
        )
        return [os.path.basename(item["path"]) for item in output]

    def walk(self, url: str) -> Generator[Tuple[str, List[str], List[str]], None, None]:
        """Recursively walk a remote directory tree, yielding ``(dirpath, subdirs, files)`` tuples.

        Args:
            url: Remote path in ``lit://[owner/][teamspace/]destination`` format.

        Returns:
            Generator[Tuple[str, List[str], List[str]], None, None]: Each tuple contains the
            current directory path, a list of its immediate subdirectory names, and a list of
            its immediate file names — mirroring the behaviour of :func:`os.walk`.
        """
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
        recursive: bool = False,
        progress_bar: bool = True,
    ) -> None:
        """Copy a file or directory between a local path and a remote ``lit://`` location.

        Exactly one of ``source`` or ``destination`` must be a ``lit://`` URL; the other
        must be a local path.  Upload is restricted to ``lightning_storage`` destinations.

        Args:
            source: Source path — either a local filesystem path or a ``lit://`` URL.
            destination: Destination path — either a local filesystem path or a ``lit://`` URL.
            recursive: When ``True``, copy directories recursively.  Required when the source
                is a remote directory or a local directory.
            progress_bar: Whether to display an upload/download progress bar.

        Raises:
            ValueError: If both paths are remote, neither path is remote, the remote file does
                not exist, or a directory is copied without ``recursive=True``.
            NotImplementedError: If the destination is a remote path that is not a
                ``lightning_storage`` location.
        """
        source_is_lit = source.startswith("lit://")
        dest_is_lit = destination.startswith("lit://")

        if source_is_lit and dest_is_lit:
            raise ValueError("Cannot copy between two remote URLs. One path must be local.")

        if not source_is_lit and not dest_is_lit:
            raise ValueError("At least one path must be a lit://")

        path_result = parse_lit_url(source if source_is_lit else destination)
        local_path = destination if source_is_lit else source

        selected_teamspace = resolve_teamspace(path_result["teamspace"], path_result["owner"])
        if source_is_lit:
            # download
            remote_path = path_result["destination"]
            parent = os.path.dirname(remote_path.strip("/"))
            entries = self._filesystem_api.list_files(selected_teamspace.id, parent, recursive=False)
            found = False
            is_directory = False

            for entry in entries:
                if os.path.basename(remote_path.strip("/")).strip("/") == os.path.basename(entry["path"]).strip("/"):
                    found = True
                    is_directory = entry.get("type") == "tree"
                    break

            if not found:
                raise ValueError(f"File {remote_path} does not exist in teamspace {selected_teamspace.name}")

            if is_directory:
                if not recursive:
                    raise ValueError(
                        f"'{remote_path}' is a directory. Use recursive=True to copy directories recursively."
                    )
                local_folder_name = os.path.basename(remote_path.rstrip("/"))
                if local_path in ("./", "."):
                    if local_folder_name == "":
                        local_folder_name = f"{selected_teamspace.name}_downloads"
                    target_path = os.path.join(local_path, local_folder_name)
                else:
                    target_path = local_path
                self._filesystem_api.download_folder(
                    path_result["destination"], target_path, selected_teamspace.id, progress_bar
                )
            else:
                if os.path.isdir(local_path) or local_path.endswith(("/", "\\")):
                    # if local_path ends with / or \ or is a directory, treat it as a directory
                    file_name = os.path.basename(path_result["destination"])
                    target_path = os.path.join(local_path, file_name)
                else:
                    target_path = local_path
                self._filesystem_api.download_file(
                    path_result["destination"], target_path, selected_teamspace.id, progress_bar
                )
        else:
            # upload
            if not _is_lightning_storage_destination(path_result["destination"] or ""):
                raise NotImplementedError("Filesystem upload is not implemented.")
            lightning_storage_upload_api.copy_local_path_to_lightning_storage(
                client=self._filesystem_api.client,
                teamspace_id=selected_teamspace.id,
                local_path=local_path,
                remote_path=destination,
                recursive=recursive,
                progress_bar=progress_bar,
            )
