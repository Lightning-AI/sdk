"""API client for identity and authorization introspection."""

from lightning_sdk.lightning_cloud.openapi import V1WhoamiResponse
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class AuthApi:
    """API client for identity and authorization introspection."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def whoami(self) -> V1WhoamiResponse:
        """Return the authenticated caller's identity.

        Works for both a personal user key and a scoped API key; a scoped key also
        reports the org, project and role it is bound to.
        """
        return self._client.auth_service_whoami()
