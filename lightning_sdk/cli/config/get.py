import click

from lightning_sdk.utils.config import Config, DefaultConfigKeys


@click.group("get")
def get() -> None:
    """Get configuration values."""


@get.command("user")
def get_user() -> None:
    """Get the default user name from the config."""
    config = Config()
    user = config.get_value(DefaultConfigKeys.user)
    click.echo(user)


@get.command("org")
def get_org() -> None:
    """Get the default organization name from the config."""
    config = Config()
    org = config.get_value(DefaultConfigKeys.organization)
    click.echo(org)


@get.command("teamspace")
def get_teamspace() -> None:
    """Get the default teamspace name from the config."""
    config = Config()
    teamspace_name = config.get_value(DefaultConfigKeys.teamspace_name)
    teamspace_owner = config.get_value(DefaultConfigKeys.teamspace_owner)
    click.echo(f"{teamspace_owner}/{teamspace_name}")


@get.command("studio")
def get_studio() -> None:
    """Get the default sutdio name from the config."""
    config = Config()
    studio = config.get_value(DefaultConfigKeys.studio)
    click.echo(studio)


@get.command("cloud-account")
def get_cloud_account() -> None:
    """Get the default cloud account name from the config."""
    config = Config()
    cloud_account = config.get_value(DefaultConfigKeys.cloud_account)
    click.echo(cloud_account)


@get.command("cloud-provider")
def get_cloud_provider() -> None:
    """Get the default cloud provider name from the config."""
    config = Config()
    cloud_provider = config.get_value(DefaultConfigKeys.cloud_provider)
    click.echo(cloud_provider)
