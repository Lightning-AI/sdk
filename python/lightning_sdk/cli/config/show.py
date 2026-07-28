import rich_click as click

from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.utils.config import Config


@click.command("show", cls=LightningCommand)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def show(as_json: bool = False) -> None:
    """Show configuration values."""
    cfg = Config()
    if as_json:
        echo_json({"config_file": cfg._config_file, **cfg._load_config()})
        return
    click.echo(cfg)
