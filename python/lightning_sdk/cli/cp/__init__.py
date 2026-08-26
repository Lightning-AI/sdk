"""CP CLI commands."""

from typing import Any, Optional

import rich_click as click

from lightning_sdk.filesystem import Filesystem
from lightning_sdk.utils.filesystem import parse_lit_url as _parse_lit_url


def parse_lit_url(url: str) -> str:
    """Parse a lit:// URL and extract its resource type (the first drive path segment)."""
    if not url.startswith("lit://"):
        raise ValueError("URL must start with 'lit://'")

    destination = _parse_lit_url(url)["destination"] or ""
    resource_type = destination.split("/")[0]
    if not resource_type:
        raise ValueError(
            f"Invalid lit URL {url!r}. Expected a resource type after the teamspace, e.g. "
            "'lit://<owner>/<teamspace>/<resource_type>/...' or 'lit:///<resource_type>/...'"
        )
    return resource_type.lower()


def _canonicalize_lit_resource_type(url: str) -> str:
    """Normalize the lit:// resource type segment to its canonical lowercase form."""
    resource_type = parse_lit_url(url)
    parsed = _parse_lit_url(url)
    destination = (parsed["destination"] or "").split("/")
    destination[0] = resource_type
    joined = "/".join(destination)
    if parsed["teamspace"] is None:
        return f"lit:///{joined}"
    return f"lit://{parsed['owner']}/{parsed['teamspace']}/{joined}"


def route_cp_operation(source: str, destination: Optional[str], **options: Any) -> None:
    """Route copy operation based on URL structure."""
    if destination is None:
        raise ValueError("Destination path must be provided.")

    source_is_lit = source.startswith("lit://")
    dest_is_lit = destination.startswith("lit://")

    if source_is_lit:
        source = _canonicalize_lit_resource_type(source)
    if dest_is_lit:
        destination = _canonicalize_lit_resource_type(destination)

    if source_is_lit and dest_is_lit:
        raise ValueError("Cannot copy between two remote URLs. One path must be local.")

    if not source_is_lit and not dest_is_lit:
        raise ValueError("At least one path must be a lit://")

    # Every resource type is a path in the teamspace drive, passed through
    # for the server to resolve. This validates the URL shape up front.
    parse_lit_url(source if source_is_lit else destination)

    return Filesystem().copy(
        source=source,
        destination=destination,
        recursive=options.get("recursive", False),
        progress_bar=options.get("progress_bar", True),
        cloud_account=options.get("cloud_account"),
    )


def register_commands(command: click.Command) -> None:
    """Register cp command callback."""

    def new_callback(source: str, destination: Optional[str], recursive: bool, **kwargs: Any) -> None:
        route_cp_operation(
            source=source,
            destination=destination,
            recursive=recursive,
            **kwargs,
        )

    command.callback = new_callback
