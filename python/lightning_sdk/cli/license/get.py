import click

from lightning_sdk.utils.config import _DEFAULT_CONFIG_FILE_PATH, Config, DefaultConfigKeys


@click.command("get")
@click.argument("product_name")
@click.option("--config-file", help="Path to the config file")
def get_license(product_name: str, config_file: str = _DEFAULT_CONFIG_FILE_PATH) -> None:
    """Get a license key for a given product."""
    cfg = Config(config_file)
    license_key = cfg.get(f"{DefaultConfigKeys.license}.{product_name}")
    if license_key:
        # echo the license key without any additional output to make parsing simpler
        click.echo(license_key)
