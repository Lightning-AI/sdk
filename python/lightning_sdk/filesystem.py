import logging
import os
import warnings
from pathlib import Path
from typing import Generator, List, Optional, Tuple

from lightning_sdk.api.filesystem_api import FilesystemApi
from lightning_sdk.api.utils import _RemoteApiError
from lightning_sdk.cli.utils.filesystem import resolve_teamspace
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.filesystem import parse_lit_url
from lightning_sdk.utils.logging import TrackCallsMeta

logger = logging.getLogger(__name__)

__all__ = [
    "Filesystem",
]


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
        remote_path = path_result["destination"] or ""
        selected_teamspace = resolve_teamspace(path_result["teamspace"], path_result["owner"])
        output = self._filesystem_api.list_files(teamspace_id=selected_teamspace.id, path=remote_path, recursive=False)
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
        remote_path = path_result["destination"] or ""
        selected_teamspace = resolve_teamspace(path_result["teamspace"], path_result["owner"])
        output = self._filesystem_api.list_files(teamspace_id=selected_teamspace.id, path=remote_path, recursive=True)

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
        cloud_account: Optional[str] = None,
    ) -> None:
        """Copy a file or directory between a local path and a remote ``lit://`` location.

        Exactly one of ``source`` or ``destination`` must be a ``lit://`` URL; the other
        must be a local path.  Remote paths are passed through to the server, so any
        destination the teamspace drive accepts works here.

        Args:
            source: Source path — either a local filesystem path or a ``lit://`` URL.
            destination: Destination path — either a local filesystem path or a ``lit://`` URL.
            recursive: When ``True``, copy directories recursively.  Required when the source
                is a remote directory or a local directory.
            progress_bar: Whether to display an upload/download progress bar.
            cloud_account: Cloud account to store uploads on.  Some destinations require
                one (e.g. ``uploads/``); others pick their own storage.

        Raises:
            ValueError: If both paths are remote, neither path is remote, the remote file does
                not exist, or a directory is copied without ``recursive=True``.
            FileNotFoundError: If a local upload source does not exist.
        """
        source_is_lit = source.startswith("lit://")
        dest_is_lit = destination.startswith("lit://")

        if source_is_lit and dest_is_lit:
            raise ValueError("Cannot copy between two remote URLs. One path must be local.")

        if not source_is_lit and not dest_is_lit:
            raise ValueError("At least one path must be a lit://")

        path_result = parse_lit_url(source if source_is_lit else destination)
        remote_path = path_result["destination"] or ""
        local_path = destination if source_is_lit else source

        selected_teamspace = resolve_teamspace(path_result["teamspace"], path_result["owner"])
        if source_is_lit:
            # download
            parent = os.path.dirname(remote_path.strip("/"))
            try:
                entries = self._filesystem_api.list_files(selected_teamspace.id, parent, recursive=False)
            except _RemoteApiError as e:
                # A missing parent means the path can't exist either.
                if e.status_code != 404:
                    raise
                raise ValueError(f"File {remote_path} does not exist in teamspace {selected_teamspace.name}") from e
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
                self._filesystem_api.download_folder(remote_path, target_path, selected_teamspace.id, progress_bar)
            else:
                if os.path.isdir(local_path) or local_path.endswith(("/", "\\")):
                    # if local_path ends with / or \ or is a directory, treat it as a directory
                    file_name = os.path.basename(remote_path)
                    target_path = os.path.join(local_path, file_name)
                else:
                    target_path = local_path
                self._filesystem_api.download_file(remote_path, target_path, selected_teamspace.id, progress_bar)
        else:
            # upload
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"The provided path does not exist: {local_path}")

            remote_dest = remote_path.replace("\\", "/").lstrip("/")
            if remote_dest.startswith("teamspace/"):
                remote_dest = remote_dest[len("teamspace/") :]

            if os.path.isdir(local_path):
                if not recursive:
                    raise ValueError(
                        f"'{local_path}' is a directory. Use recursive=True to copy directories recursively."
                    )
                root = remote_dest.strip("/")
                for file_path in sorted(p for p in Path(local_path).rglob("*") if p.is_file()):
                    relative = file_path.relative_to(local_path).as_posix()
                    cloud_account = self._upload_file(
                        selected_teamspace,
                        file_path=str(file_path),
                        remote_path=f"{root}/{relative}" if root else relative,
                        progress_bar=progress_bar,
                        cloud_account=cloud_account,
                    )
            else:
                target = remote_dest
                directory_target = (
                    target.endswith("/")
                    or not target.strip("/")
                    or self._is_remote_directory(selected_teamspace.id, target)
                )
                if directory_target:
                    target = f"{target.strip('/')}/{os.path.basename(local_path)}".lstrip("/")
                self._upload_file(
                    selected_teamspace,
                    file_path=local_path,
                    remote_path=target,
                    progress_bar=progress_bar,
                    cloud_account=cloud_account,
                )

    def _upload_file(
        self,
        teamspace: Teamspace,
        file_path: str,
        remote_path: str,
        progress_bar: bool,
        cloud_account: Optional[str],
    ) -> Optional[str]:
        """Upload one file, deferring to the teamspace default cloud account when the server asks for one.

        Some destinations need a cloud account to store the file on, and the server
        names that demand in its rejection; retry with the teamspace default rather
        than making callers know which destinations those are.  Returns the cloud
        account to reuse for the remaining files of the same copy.
        """
        try:
            self._filesystem_api.upload_file(
                teamspace_id=teamspace.id,
                file_path=file_path,
                remote_path=remote_path,
                progress_bar=progress_bar,
                cloud_account=cloud_account,
            )
            return cloud_account
        except _RemoteApiError as e:
            # The server has no structured error codes yet, so its message is
            # the only way to recognize the demand.
            cluster_demanded = e.status_code == 400 and "ClusterID" in e.server_message
            if cloud_account is not None or not cluster_demanded:
                raise
            default = getattr(teamspace, "default_cloud_account", None)
            if not default:
                raise RuntimeError(
                    f"A cloud account is required to upload to {remote_path!r} and the teamspace "
                    "has no default. Pass cloud_account to pick one."
                ) from e
            warnings.warn(f"No cloud account specified. Using teamspace default cloud account: {default}.")
            self._filesystem_api.upload_file(
                teamspace_id=teamspace.id,
                file_path=file_path,
                remote_path=remote_path,
                progress_bar=progress_bar,
                cloud_account=default,
            )
            return default

    def _is_remote_directory(self, teamspace_id: str, remote_path: str) -> bool:
        """Whether ``remote_path`` names an existing remote directory.

        Mirrors ``cp`` semantics: copying a file onto an existing directory puts the
        file inside it.  A path that cannot be listed is treated as not-a-directory,
        so the upload proceeds and any real problem surfaces from the upload itself.
        """
        parent, _, name = remote_path.strip("/").rpartition("/")
        try:
            entries = self._filesystem_api.list_files(teamspace_id, parent, recursive=False)
        except RuntimeError:
            return False
        return any(
            os.path.basename(str(entry.get("path", "")).rstrip("/")) == name and entry.get("type") == "tree"
            for entry in entries
        )
