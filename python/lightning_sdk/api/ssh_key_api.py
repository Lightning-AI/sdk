import json

from lightning_sdk.api.utils import ApiException, cached_lightning_client
from lightning_sdk.lightning_cloud.openapi import V1CreateSSHPublicKeyRequest, V1SSHPublicKey


class SSHKeyRegistrationError(Exception):
    """The platform refused to register an SSH public key. The message is the platform's own, for the user."""


def _error_message(e: ApiException) -> str:
    body = e.body.decode(errors="replace") if isinstance(e.body, bytes) else e.body
    try:
        message = json.loads(body or "")["message"]
    except (ValueError, KeyError, TypeError):
        message = ""
    return message or f"HTTP {e.status} {e.reason}"


class SSHKeyApi:
    """Internal API client for the SSH public keys registered to the signed-in user."""

    def create_public_key(self, name: str, public_key: str) -> V1SSHPublicKey:
        """Register ``public_key`` under ``name``. If the account already has it, the platform returns it unchanged.

        Raises:
            SSHKeyRegistrationError: With the platform's reason, e.g. that the key is held by another account.
        """
        # Not retried: once retries run out, the client raises a bare Exception without the platform's message.
        client = cached_lightning_client(retry=False)
        try:
            return client.s_sh_public_key_service_create_ssh_public_key(
                V1CreateSSHPublicKeyRequest(name=name, public_key=public_key)
            )
        except ApiException as e:
            raise SSHKeyRegistrationError(_error_message(e)) from None
