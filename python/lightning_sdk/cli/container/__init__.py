"""Container CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register container commands with the given group."""
    from lightning_sdk.cli.container.delete import LitContainer, resolve_container_delete
    from lightning_sdk.cli.container.download import download_container
    from lightning_sdk.cli.container.list import list_containers
    from lightning_sdk.cli.container.upload import upload_container
    from lightning_sdk.cli.utils.delete import register_delete_command

    group.add_command(list_containers, name="list")
    group.add_command(upload_container, name="upload")
    group.add_command(download_container, name="download")
    register_delete_command(
        group,
        LitContainer,
        label="Container",
        help="Delete the docker container NAME.",
        context_help=(
            "The teamspace to delete the container from. "
            "Should be specified as {owner}/{name}. "
            "Defaults to the configured teamspace."
        ),
        resolve_delete=resolve_container_delete,
    )
