

def login() -> None:
    """Authorize the CLI to access Grid AI resources for a particular user.

    Use login command to force authenticate, a web browser will open to complete the authentication.
    """
    from lightning_sdk.lightning_cloud.login import Auth  # local to avoid circular import

    auth = Auth()
    auth.clear()
    auth._run_server()

def logout() -> None:
    """Logout from LightningCloud"""
    from lightning_sdk.lightning_cloud.login import Auth  # local to avoid circular import

    Auth.clear()


def main() -> None:
    """CLI entrypoint."""
    from fire import Fire

    Fire({"login": login, "logout": logout})


if __name__ == "__main__":
    main()
