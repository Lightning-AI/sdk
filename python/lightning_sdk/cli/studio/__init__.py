"""Studio CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register studio commands with the given group."""
    from lightning_sdk.cli.legacy_redirects import mark_deprecated_command
    from lightning_sdk.cli.studio.connect import connect_studio
    from lightning_sdk.cli.studio.cp import cp_studio_file
    from lightning_sdk.cli.studio.create import create_studio
    from lightning_sdk.cli.studio.env import env
    from lightning_sdk.cli.studio.list import list_studios
    from lightning_sdk.cli.studio.ls import ls_studio
    from lightning_sdk.cli.studio.open import open_studio
    from lightning_sdk.cli.studio.rm import rm_studio_file
    from lightning_sdk.cli.studio.ssh import ssh_studio
    from lightning_sdk.cli.studio.start import start_studio
    from lightning_sdk.cli.studio.stop import stop_studio
    from lightning_sdk.cli.studio.switch import switch_studio
    from lightning_sdk.cli.utils.delete import register_delete_command
    from lightning_sdk.studio import Studio

    register_delete_command(
        group,
        Studio,
        label="Studio",
        help="Delete a Studio.",
        context_help="Override default teamspace (format: owner/teamspace).",
        resource_kwargs={"create_ok": False},
    )
    group.add_command(env)
    group.add_command(create_studio)
    group.add_command(list_studios)
    group.add_command(ssh_studio)
    group.add_command(start_studio)
    group.add_command(stop_studio)
    group.add_command(switch_studio)
    group.add_command(connect_studio)
    # The replacements take full drive URLs, not this group's short studio forms, so the
    # warning spells out the conversion — a bare command rename could target a different drive.
    url_note = (
        "Note the URL format differs: use lit://<owner>/<teamspace>/studios/<studio>/<path>, "
        "or lit:///studios/<studio>/<path> for the current teamspace."
    )
    group.add_command(mark_deprecated_command(cp_studio_file, "lightning cp", detail=url_note))
    group.add_command(mark_deprecated_command(ls_studio, "lightning ls", detail=url_note))
    group.add_command(mark_deprecated_command(rm_studio_file, "lightning rm", detail=url_note))
    group.add_command(open_studio, name="open")
