import click


@click.group()
def main():
    pass


@main.command()
def login():
    """Authorize the CLI to access Grid AI resources for a particular user.
    Use login command to force authenticate,
    a web browser will open to complete the authentication.
    """
    from lightning_sdk.lightning_cloud.login import Auth  # local to avoid circular import

    auth = Auth()
    auth.clear()
    auth._run_server()


@main.command()
def logout():
    """Logout from LightningCloud"""
    from lightning_sdk.lightning_cloud.login import Auth  # local to avoid circular import

    Auth.clear()
