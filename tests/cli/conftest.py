def fixture_reset_auth(autouse=True, scope="function"):
    """Reset the auth state before and after each test."""
    from lightning_sdk.lightning_cloud.login import Auth

    auth = Auth()
    auth.clear()
    yield
    auth.clear()
