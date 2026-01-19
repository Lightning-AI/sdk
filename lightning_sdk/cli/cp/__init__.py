"""CP CLI commands."""

from typing import Any, Literal, Optional

import click

from lightning_sdk.cli.studio.cp import cp_download as studio_cp_download
from lightning_sdk.cli.studio.cp import cp_upload as studio_cp_upload


def parse_lit_url(url: str) -> tuple[str, list[str], Literal["studios", "uploads"]]:
    """Parse lit:// URL and extract resource type."""
    if "://" not in url:
        raise ValueError("URL must contain '://'")

    path = url.split("://")[-1].split("/")

    if path[2] == "studios":
        resource_type = "studios"
    elif "uploads" in path[3]:
        resource_type = "uploads"
    else:
        raise ValueError("URL must contain either 'studios' or 'uploads'")

    return resource_type


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
            return studio_cp_download(source, destination, options)
        raise ValueError(f"Resource type: {resource_type} is not supported")
    else:
        resource_type = parse_lit_url(destination)
        if resource_type == "studios":
            return studio_cp_upload(source, destination, options)
        raise ValueError(f"Resource type: {resource_type} is not supported")


def register_commands(command: click.Command) -> None:
    """Register cp command callback."""

    def new_callback(source: str, destination: Optional[str], recursive: bool, **kwargs: Any) -> None:
        try:
            route_cp_operation(
                source=source,
                destination=destination,
                recursive=recursive,
            )
        except Exception:
            raise

    command.callback = new_callback
