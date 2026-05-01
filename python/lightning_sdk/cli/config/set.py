import click

from lightning_sdk.cli.utils.save_to_config import save_teamspace_to_config
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.machine import CloudProvider
from lightning_sdk.studio import Studio
from lightning_sdk.utils.config import Config, DefaultConfigKeys
from lightning_sdk.utils.resolve import _resolve_org, _resolve_user


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
    menu = TeamspacesMenu()
    teamspace_resolved = menu(teamspace=teamspace_name)

    # explicit user action, so overwrite the config
    save_teamspace_to_config(teamspace_resolved, overwrite=True)


@set_value.command("cloud-account")
@click.argument("cloud_account_name")
def set_cloud_account(cloud_account_name: str) -> None:
    """Set the default cloud account name in the config."""
    config = Config()
    setattr(config, DefaultConfigKeys.cloud_account, cloud_account_name)


@set_value.command("cloud-provider")
@click.argument("cloud_provider_name")
def set_cloud_provider(cloud_provider_name: str) -> None:
    """Set the default cloud provider name in the config."""
    config = Config()

    try:
        cloud_provider = CloudProvider(cloud_provider_name)
    except ValueError:
        # TODO: make this a generic CLI error
        raise ValueError(
            f"Could not resolve cloud provider: '{cloud_provider_name}'. "
            f"Supported values are: {', '.join(m.name for m in list(CloudProvider))}"
        ) from None

    setattr(config, DefaultConfigKeys.cloud_provider, cloud_provider.name)
