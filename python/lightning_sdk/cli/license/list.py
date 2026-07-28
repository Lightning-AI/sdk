"""License list command."""

from typing import Mapping

import rich_click as click
from rich.table import Table

from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.utils.config import _DEFAULT_CONFIG_FILE_PATH, Config, DefaultConfigKeys


@click.command("list", cls=LightningCommand)
@click.option("--include-key", help="Print the key as well", is_flag=True)
@click.option("--config-file", help="Path to the config file")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_licenses(include_key: bool, config_file: str = _DEFAULT_CONFIG_FILE_PATH, as_json: bool = False) -> None:
    """List configured licenses.

    Example:
        lightning license list --include-key

    """
    return list_impl(include_key=include_key, config_path=config_file, as_json=as_json)


def list_impl(include_key: bool, config_path: str, as_json: bool = False) -> None:
    cfg = Config(config_file=config_path)

    license_cfg = cfg.get_sub_config(DefaultConfigKeys.license)
    entries = sorted(license_cfg.items(), key=lambda x: x[0]) if isinstance(license_cfg, Mapping) else []

    if as_json:
        echo_json(
            [
                {"product": product_name, "license_key": license_key if include_key else "********"}
                for product_name, license_key in entries
            ]
        )
        return

    if not isinstance(license_cfg, Mapping):
        click.echo("No licenses configured!")
        return

    table = Table(
        pad_edge=True,
    )
    table.add_column("Product")
    table.add_column("License Key")
    for product_name, license_key in entries:
        table.add_row(product_name, license_key if include_key else "********")

    click.echo(rich_to_str(table), color=True)
