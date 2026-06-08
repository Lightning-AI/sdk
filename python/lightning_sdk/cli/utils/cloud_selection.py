from typing import Optional

import click


def warn_deprecated_cloud_options(cloud_account: Optional[str] = None, cloud_provider: Optional[str] = None) -> None:
    if cloud_account is not None:
        click.echo("Warning: --cloud-account is deprecated. Use --cloud instead.", err=True)
    if cloud_provider is not None:
        click.echo("Warning: --cloud-provider is deprecated. Use --cloud instead.", err=True)
