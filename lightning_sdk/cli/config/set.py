import click

from lightning_sdk.organization import Organization
from lightning_sdk.studio import Studio
from lightning_sdk.utils.config import Config, DefaultConfigKeys
from lightning_sdk.utils.resolve import _resolve_org, _resolve_teamspace, _resolve_user


@click.group("set")
def set_value() -> None:
    """Set configuration values."""


@set_value.command("user")
@click.argument("user_name")
def set_user(user_name: str) -> None:
    """Set the default user name in the config."""
    try:
        _resolve_user(user_name)
    except Exception:
        # TODO: make this a generic CLI error
        raise ValueError(f"Could not resolve user: '{user_name}'. Does the user exist?") from None

    config = Config()
    setattr(config, DefaultConfigKeys.user, user_name)


@set_value.command("org")
@click.argument("org_name")
def set_org(org_name: str) -> None:
    """Set the default organization name in the config."""
    try:
        _resolve_org(org_name)
    except Exception:
        # TODO: make this a generic CLI error
        raise ValueError(f"Could not resolve organization: '{org_name}'. Does the organization exist?") from None

    config = Config()
    setattr(config, DefaultConfigKeys.organization, org_name)


@set_value.command("studio")
@click.argument("studio_name")
def set_studio(studio_name: str) -> None:
    """Set the default studio name in the config."""
    try:
        studio = Studio(studio_name)
    except Exception:
        # TODO: make this a generic CLI error
        raise ValueError(f"Could not resolve studio: '{studio_name}'. Does the studio exist?") from None

    config = Config()
    setattr(config, DefaultConfigKeys.studio, studio.name)


@set_value.command("teamspace")
@click.argument("teamspace_name")
def set_teamspace(teamspace_name: str) -> None:
    """Set the default teamspace name in the config."""
    config = Config()

    splits = teamspace_name.split("/")
    teamspace_resolved = None
    if len(splits) == 1:
        try:
            teamspace_resolved = _resolve_teamspace(teamspace_name, None, None)
        except Exception:
            teamspace_resolved = None

    elif len(splits) == 2:
        try:
            try:
                teamspace_resolved = _resolve_teamspace(splits[1], splits[0], None)
            except Exception:
                teamspace_resolved = _resolve_teamspace(splits[1], None, splits[0])
        except Exception:
            teamspace_resolved = None

    if teamspace_resolved is None:
        # TODO: make this a generic CLI error
        raise ValueError(
            f"Could not resolve teamspace: '{teamspace_name}'. "
            "Teamspace should be specified as 'owner/name'. Does the teamspace exist?"
        )

    setattr(config, DefaultConfigKeys.teamspace_name, teamspace_resolved.name)
    setattr(config, DefaultConfigKeys.teamspace_owner, teamspace_resolved.owner.name)
    if isinstance(teamspace_resolved.owner, Organization):
        setattr(config, DefaultConfigKeys.teamspace_owner_type, "organization")
    else:
        setattr(config, DefaultConfigKeys.teamspace_owner_type, "user")
