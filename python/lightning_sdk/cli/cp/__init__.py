"""CP CLI commands."""

from typing import Any, Optional

import rich_click as click

from lightning_sdk.filesystem import Filesystem


def route_cp_operation(source: str, destination: Optional[str], **options: Any) -> None:
    """Route copy operation based on URL structure.

    Drive paths are passed through untouched — the server owns their validation
    (resource types, case, existence).
    """
    if destination is None:
        raise ValueError("Destination path must be provided.")

    source_is_lit = source.startswith("lit://")
    dest_is_lit = destination.startswith("lit://")

    if source_is_lit and dest_is_lit:
        raise ValueError("Cannot copy between two remote URLs. One path must be local.")

    if not source_is_lit and not dest_is_lit:
        raise ValueError("At least one path must be a lit://")

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
