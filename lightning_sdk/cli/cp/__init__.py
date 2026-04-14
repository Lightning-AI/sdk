"""CP CLI commands."""

from typing import Any, Literal, Optional

import click

from lightning_sdk.cli.cp.teamspace_uploads import cp_upload as teamspace_uploads_cp_upload
from lightning_sdk.cli.studio.cp import cp_download as studio_cp_download
from lightning_sdk.cli.studio.cp import cp_upload as studio_cp_upload
from lightning_sdk.filesystem.filesystem import Filesystem


def parse_lit_url(url: str) -> tuple[str, list[str], Literal["studios", "uploads"]]:
    """Parse lit:// URL and extract resource type."""
    if "://" not in url:
        raise ValueError("URL must contain '://'")

    path = url.split("://")[-1].split("/")
    return path[2].lower()


def route_cp_operation(source: str, destination: str, **options: Any) -> None:
    """Route copy operation based on URL structure."""
    source_is_lit = source.startswith("lit://")
    dest_is_lit = destination.startswith("lit://")

    if source_is_lit and dest_is_lit:
        raise ValueError("Cannot copy between two remote URLs. One path must be local.")

    if not source_is_lit and not dest_is_lit:
        raise ValueError("At least one path must be a lit://")

    if source_is_lit:
        resource_type = parse_lit_url(source)
        if resource_type == "studios":
            return studio_cp_download(source, destination, options.get("recursive", False))
        if (
            resource_type == "lightning_storage"
            or resource_type == "uploads"
            or resource_type == "s3_folders"
            or resource_type == "jobs"
            or resource_type == "gcs_folders"
            or resource_type == "s3_connections"
            or resource_type == "gcs_connections"
        ):
            fs = Filesystem()
            source = source.replace("uploads/", "Uploads/")
            return fs.copy(source=source, destination=destination, recursive=options.get("recursive", False))
        raise ValueError(f"Resource type: {resource_type} is not supported")
    else:
        resource_type = parse_lit_url(destination)
        if resource_type == "studios":
            return studio_cp_upload(source, destination, options.get("recursive", False))
        if resource_type == "uploads":
            return teamspace_uploads_cp_upload(source, destination, options)
        raise ValueError(f"Resource type: {resource_type} is not supported")


def register_commands(command: click.Command) -> None:
    """Register cp command callback."""

    def new_callback(source: str, destination: Optional[str], recursive: bool, **kwargs: Any) -> None:
        route_cp_operation(
            source=source,
            destination=destination,
            recursive=recursive,
        )

    command.callback = new_callback
