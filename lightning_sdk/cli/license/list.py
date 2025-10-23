"""License list command."""

from typing import Mapping

import click
from rich.table import Table

from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.utils.config import _DEFAULT_CONFIG_FILE_PATH, Config, DefaultConfigKeys


@click.command("list")
@click.option("--include-key", help="Print the key as well", is_flag=True)
@click.option("--config-file", help="Path to the config file")
def list_licenses(include_key: bool, config_file: str = _DEFAULT_CONFIG_FILE_PATH) -> None:
    """List configured licenses.

    Example:
        lightning license list --include-key

    """
    return list_impl(include_key=include_key, config_path=config_file)


def list_impl(include_key: bool, config_path: str) -> None:
    cfg = Config(config_file=config_path)

    license_cfg = cfg.get_sub_config(DefaultConfigKeys.license)

    if isinstance(license_cfg, Mapping):
        table = Table(
            pad_edge=True,
        )

        table.add_column("Product")
        table.add_column("License Key")

        # sort by product_name
        for product_name, license_key in sorted(license_cfg.items(), key=lambda x: x[0]):
            table.add_row(product_name, license_key if include_key else "********")

        click.echo(rich_to_str(table), color=True)

    else:
        click.echo("No licenses configured!")
