import click

from lightning_sdk.utils.config import _DEFAULT_CONFIG_FILE_PATH, Config, DefaultConfigKeys


@click.command("set")
@click.argument("product_name")
@click.argument("license_key")
@click.option("--config-file", help="Path to the config file")
def set_license(product_name: str, license_key: str, config_file: str = _DEFAULT_CONFIG_FILE_PATH) -> None:
    """Set a license key for a given product."""
    cfg = Config(config_file)
    cfg.set(f"{DefaultConfigKeys.license}.{product_name}", license_key)
