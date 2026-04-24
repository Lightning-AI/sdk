import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from time import monotonic, sleep
from typing import Any, List, Optional, Tuple, Type, Union

from lightning_sdk.api.utils import _FileUploader
from lightning_sdk.lightning_cloud.openapi import DataConnectionServiceCreateDataConnectionBody, V1R2DataConnection
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.utils.filesystem import parse_lit_url

LIGHTNING_STORAGE_READY_STATE = "DATA_CONNECTION_STATE_CREATED"
LIGHTNING_STORAGE_POLL_INTERVAL_SECONDS = 2
LIGHTNING_STORAGE_POLL_TIMEOUT_SECONDS = 30


def _validate_remote_part(part: str) -> str:
    part = str(part)
    if PurePosixPath(part).is_absolute():
        raise ValueError(f"Remote path parts must be relative: {part!r}")
    if part == "..":
        raise ValueError("Remote path parts must not be '..'")
    if "/" in part or "\\" in part:
        raise ValueError(f"Remote path parts must not contain path separators: {part!r}")
    return part


def _join_remote_parts(*parts: str) -> str:
    normalized_parts = [_validate_remote_part(part) for part in parts if part not in ("", ".", "/")]
    if not normalized_parts:
        return ""
    return PurePosixPath(*normalized_parts).as_posix()


def _normalize_remote_path(remote_path: str) -> str:
    return str(remote_path or "").strip().replace("\\", "/")


@dataclass
class LightningStorageUploadTarget:
    data_connection_id: str
    cloud_account: Optional[str]
    folder_name: str
    relative_parts: Tuple[str, ...]

    def absolute_path(self, *parts: str) -> str:
        return "/" + _join_remote_parts(
            "teamspace", "lightning_storage", self.folder_name, *self.relative_parts, *parts
        )

    def remote_path(self, *parts: str) -> str:
        return _join_remote_parts(*self.relative_parts, *parts)


def resolve_lightning_storage_upload_target(
    *,
    client: Any,
    teamspace_id: str,
    remote_path: str,
    cloud_account: Optional[str] = None,
) -> LightningStorageUploadTarget:
    folder_name, relative_parts = _parse_lightning_storage_path(remote_path)
    return _resolve_lightning_storage_upload_target_from_parts(
        client=client,
        teamspace_id=teamspace_id,
        folder_name=folder_name,
        relative_parts=relative_parts,
        cloud_account=cloud_account,
    )


def copy_local_path_to_lightning_storage(
    *,
    client: Any,
    teamspace_id: str,
    local_path: Union[os.PathLike, str],
    remote_path: str,
    recursive: bool = False,
    progress_bar: bool = True,
    cloud_account: Optional[str] = None,
    uploader_cls: Optional[Type[Any]] = None,
) -> List[str]:
    """Copy a local file or directory into ``lightning_storage``.

    Single-file uploads mirror ``cp`` semantics:
    - a ``remote_path`` ending with ``/`` is treated as a directory target and preserves ``local_path.name``
    - otherwise, the last segment is treated as the explicit destination filename

    Recursive directory uploads also mirror ``cp -r`` semantics:
    - ``remote_path`` is treated as the destination directory root
    - files under ``local_path`` keep their relative paths beneath that root
    """
    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"The provided path does not exist: {local_path}")

    if local_path.is_dir():
        if not recursive:
            raise ValueError(f"'{local_path}' is a directory. Use recursive=True to copy directories recursively.")
        return _copy_local_directory_to_lightning_storage(
            client=client,
            teamspace_id=teamspace_id,
            local_path=local_path,
            remote_path=remote_path,
            progress_bar=progress_bar,
            cloud_account=cloud_account,
            uploader_cls=uploader_cls,
        )

    return [
        _copy_local_file_to_lightning_storage(
            client=client,
            teamspace_id=teamspace_id,
            local_path=local_path,
            remote_path=remote_path,
            progress_bar=progress_bar,
            cloud_account=cloud_account,
            uploader_cls=uploader_cls,
        )
    ]


def upload_file_to_resolved_lightning_storage_target(
    *,
    client: Any,
    teamspace_id: str,
    upload_target: LightningStorageUploadTarget,
    local_path: Union[os.PathLike, str],
    destination_parts: Tuple[str, ...] = (),
    progress_bar: bool = False,
    uploader_cls: Optional[Type[Any]] = None,
) -> str:
    uploader_cls = _FileUploader if uploader_cls is None else uploader_cls
    local_path = Path(local_path)
    destination_parts = tuple(destination_parts)

    uploader_cls(
        client=client,
        teamspace_id=teamspace_id,
        cloud_account=upload_target.cloud_account,
        data_connection_id=upload_target.data_connection_id,
        file_path=str(local_path),
        remote_path=upload_target.remote_path(*destination_parts),
        progress_bar=progress_bar,
    )()
    return upload_target.absolute_path(*destination_parts)


def _copy_local_file_to_lightning_storage(
    *,
    client: Any,
    teamspace_id: str,
    local_path: Path,
    remote_path: str,
    progress_bar: bool,
    cloud_account: Optional[str],
    uploader_cls: Optional[Type[Any]],
) -> str:
    normalized_remote_path = _normalize_remote_path(remote_path)
    folder_name, relative_parts = _parse_lightning_storage_path(normalized_remote_path)
    directory_target = normalized_remote_path.endswith("/") or not relative_parts

    if directory_target:
        upload_target = _resolve_lightning_storage_upload_target_from_parts(
            client=client,
            teamspace_id=teamspace_id,
            folder_name=folder_name,
            relative_parts=relative_parts,
            cloud_account=cloud_account,
        )
        destination_parts = (local_path.name,)
    else:
        upload_target = _resolve_lightning_storage_upload_target_from_parts(
            client=client,
            teamspace_id=teamspace_id,
            folder_name=folder_name,
            relative_parts=relative_parts[:-1],
            cloud_account=cloud_account,
        )
        destination_parts = (relative_parts[-1],)

    return upload_file_to_resolved_lightning_storage_target(
        client=client,
        teamspace_id=teamspace_id,
        upload_target=upload_target,
        local_path=local_path,
        destination_parts=destination_parts,
        progress_bar=progress_bar,
        uploader_cls=uploader_cls,
    )


def _copy_local_directory_to_lightning_storage(
    *,
    client: Any,
    teamspace_id: str,
    local_path: Path,
    remote_path: str,
    progress_bar: bool,
    cloud_account: Optional[str],
    uploader_cls: Optional[Type[Any]],
) -> List[str]:
    upload_target = resolve_lightning_storage_upload_target(
        client=client,
        teamspace_id=teamspace_id,
        remote_path=remote_path,
        cloud_account=cloud_account,
    )
    uploaded_paths = []
    files = sorted(path for path in local_path.rglob("*") if path.is_file())
    for file_path in files:
        relative_parts = PurePosixPath(file_path.relative_to(local_path).as_posix()).parts
        uploaded_paths.append(
            upload_file_to_resolved_lightning_storage_target(
                client=client,
                teamspace_id=teamspace_id,
                upload_target=upload_target,
                local_path=file_path,
                destination_parts=relative_parts,
                progress_bar=progress_bar,
                uploader_cls=uploader_cls,
            )
        )
    return uploaded_paths


def _resolve_lightning_storage_upload_target_from_parts(
    *,
    client: Any,
    teamspace_id: str,
    folder_name: str,
    relative_parts: Tuple[str, ...],
    cloud_account: Optional[str] = None,
) -> LightningStorageUploadTarget:
    cloud_account = cloud_account or _resolve_lightning_storage_upload_cloud_account(
        client=client, teamspace_id=teamspace_id
    )
    data_connection = _get_or_create_lightning_storage_folder(
        client=client,
        teamspace_id=teamspace_id,
        folder_name=folder_name,
    )
    data_connection_id = getattr(data_connection, "id", None)
    if not data_connection_id:
        raise RuntimeError(f"lightning_storage folder '{folder_name}' is missing an id")

    return LightningStorageUploadTarget(
        data_connection_id=data_connection_id,
        cloud_account=cloud_account,
        folder_name=folder_name,
        relative_parts=relative_parts,
    )


def _extract_lit_remote_destination(remote_path: str) -> str:
    parsed = parse_lit_url(remote_path)
    return str(parsed.get("destination") or "").strip("/")


def _parse_lightning_storage_path(remote_path: str) -> Tuple[str, Tuple[str, ...]]:
    normalized = _normalize_remote_path(remote_path)
    if not normalized:
        raise ValueError("remote_path must not be empty")

    if normalized.startswith("lit://"):
        normalized = _extract_lit_remote_destination(normalized)

    matched_lightning_storage_prefix = False
    for prefix in ("/teamspace/lightning_storage", "teamspace/lightning_storage", "lightning_storage"):
        if normalized == prefix:
            normalized = ""
            matched_lightning_storage_prefix = True
            break
        if normalized.startswith(prefix + "/"):
            normalized = normalized[len(prefix) + 1 :].lstrip("/")
            matched_lightning_storage_prefix = True
            break

    if not matched_lightning_storage_prefix:
        raise ValueError("remote_path currently supports lightning_storage destinations only")

    parts = [_validate_remote_part(part) for part in PurePosixPath(normalized).parts if part not in ("", ".", "/")]
    if not parts:
        raise ValueError("remote_path must include a lightning_storage folder name")

    return parts[0], tuple(parts[1:])


def _get_or_create_lightning_storage_folder(
    *,
    client: Any,
    teamspace_id: str,
    folder_name: str,
) -> Any:
    existing = _find_lightning_storage_folder(client=client, teamspace_id=teamspace_id, folder_name=folder_name)
    if existing is not None:
        return _wait_for_lightning_storage_folder_ready(
            client=client,
            teamspace_id=teamspace_id,
            folder_name=folder_name,
            initial_connection=existing,
        )

    body = DataConnectionServiceCreateDataConnectionBody(
        name=folder_name,
        create_resources=True,
        force=True,
        writable=True,
        r2=V1R2DataConnection(name=folder_name),
    )
    try:
        client.data_connection_service_create_data_connection(body=body, project_id=teamspace_id)
    except ApiException as ex:
        error_body = str(getattr(ex, "body", ex))
        if "duplicate key value violates unique constraint" not in error_body:
            raise

    return _wait_for_lightning_storage_folder_ready(
        client=client,
        teamspace_id=teamspace_id,
        folder_name=folder_name,
    )


def _resolve_lightning_storage_upload_cloud_account(*, client: Any, teamspace_id: str) -> str:
    cloud_account = os.getenv("LIGHTNING_CLUSTER_ID")
    if cloud_account:
        return cloud_account

    cluster_bindings = list(
        getattr(client.projects_service_list_project_cluster_bindings(project_id=teamspace_id), "clusters", None) or []
    )
    cluster_ids = [binding.cluster_id for binding in cluster_bindings if getattr(binding, "cluster_id", None)]
    if len(cluster_ids) == 1:
        return cluster_ids[0]

    preferred_cluster = getattr(
        getattr(client.projects_service_get_project(teamspace_id), "project_settings", None),
        "preferred_cluster",
        None,
    )
    if preferred_cluster:
        return preferred_cluster

    if not cluster_ids:
        raise RuntimeError(
            "Could not determine the current cloud account for lightning_storage upload "
            "because no clusters are bound to the teamspace"
        )

    raise RuntimeError(
        "Could not determine the current cloud account for lightning_storage upload. "
        f"Choices are: {', '.join(cluster_ids)}"
    )


def _find_lightning_storage_folder(*, client: Any, teamspace_id: str, folder_name: str) -> Optional[Any]:
    response = client.data_connection_service_list_data_connections(project_id=teamspace_id)
    for connection in list(getattr(response, "data_connections", None) or []):
        if getattr(connection, "name", None) != folder_name:
            continue
        if getattr(connection, "r2", None) is None:
            raise ValueError(f"data connection '{folder_name}' exists but is not a lightning_storage folder")
        if getattr(connection, "writable", None) is False:
            raise ValueError(f"lightning_storage folder '{folder_name}' is not writable")
        return connection
    return None


def _is_lightning_storage_folder_ready(connection: Any) -> bool:
    if connection is None:
        return False

    r2 = getattr(connection, "r2", None)
    if r2 is None:
        return False

    state = str(getattr(connection, "state", "") or "")
    source = str(getattr(r2, "source", "") or "")
    account_id = str(getattr(r2, "account_id", "") or "")

    return (
        state == LIGHTNING_STORAGE_READY_STATE
        and source.startswith("r2://")
        and source != "tmp"
        and account_id not in ("", "tmp")
    )


def _wait_for_lightning_storage_folder_ready(
    *,
    client: Any,
    teamspace_id: str,
    folder_name: str,
    initial_connection: Optional[Any] = None,
    timeout_seconds: int = LIGHTNING_STORAGE_POLL_TIMEOUT_SECONDS,
    poll_interval_seconds: int = LIGHTNING_STORAGE_POLL_INTERVAL_SECONDS,
) -> Any:
    connection = initial_connection
    deadline = monotonic() + timeout_seconds
    first_poll = initial_connection is None

    while True:
        if _is_lightning_storage_folder_ready(connection):
            return connection

        remaining = deadline - monotonic()
        if remaining <= 0:
            break

        if not first_poll:
            sleep(min(poll_interval_seconds, remaining))

        connection = _find_lightning_storage_folder(
            client=client,
            teamspace_id=teamspace_id,
            folder_name=folder_name,
        )
        first_poll = False

    state = getattr(connection, "state", None)
    r2 = getattr(connection, "r2", None)
    source = getattr(r2, "source", None) if r2 is not None else None
    raise RuntimeError(
        f"lightning_storage folder '{folder_name}' was not ready for upload within {timeout_seconds}s "
        f"(state={state}, source={source})"
    )
