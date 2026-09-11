"""Cloud instance CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register cloud instance commands with the given group."""
    from lightning_sdk.cli.instance.commands import (
        create_instance,
        get_instance,
        list_instance_images,
        list_instance_types,
        list_instances,
        resolve_instance_delete,
        ssh_instance,
    )
    from lightning_sdk.cli.utils.delete import register_delete_command

    group.add_command(list_instances, name="list")
    group.add_command(get_instance, name="get")
    group.add_command(create_instance, name="create")
    register_delete_command(
        group,
        label="Instance",
        help="""Delete a cloud instance and its volume.

        Example:
          $ lightning instance delete my-vm

          Instance deleted
        """,
        identifier="name_or_id",
        context_option="org",
        context_help="The organization owning the instance. Defaults to the current organization.",
        resolve_delete=resolve_instance_delete,
    )
    group.add_command(ssh_instance, name="ssh")
    group.add_command(list_instance_images, name="images")
    group.add_command(list_instance_types, name="types")
