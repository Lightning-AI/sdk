"""Short-lived credentials for the buckets behind teamspace data connections."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

__all__ = ["BucketCredentials"]


@dataclass(frozen=True)
class BucketCredentials:
    """Short-lived credentials for the bucket behind a data connection.

    These expire — usually within the hour — so they are meant to be fetched when
    needed rather than held. ``expires_at`` is the deadline to refresh against, and is
    ``None`` only for connections backed by static keys, which do not expire.

    ``region`` and ``endpoint`` are part of the answer, not decoration. Inside a Studio
    the default AWS profile can point at Lightning Storage, and botocore will apply that
    profile's endpoint to any client built without one — which sends an AWS request to
    Cloudflare and gets it rejected as ``InvalidAccessKeyId``. Pass these through rather
    than letting a client resolve its own.
    """

    access_key_id: str
    secret_access_key: str
    session_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    region: Optional[str] = None
    endpoint: Optional[str] = None

    def to_credential_process(self) -> Dict[str, Any]:
        """Render as the JSON payload AWS's ``credential_process`` expects.

        Any tool that understands that setting — the AWS CLI, boto3, rclone, s5cmd, the
        Go and Java SDKs — will re-run the process to refresh once ``Expiration`` passes,
        which is what makes the short lifetime survivable without per-tool support.

        ``Expiration`` is omitted for credentials that never expire, which AWS reads as
        "cache indefinitely".

        Returns:
            The credential payload, ready to be serialised to stdout as JSON.
        """
        payload: Dict[str, Any] = {
            "Version": 1,
            "AccessKeyId": self.access_key_id,
            "SecretAccessKey": self.secret_access_key,
        }

        if self.session_token:
            payload["SessionToken"] = self.session_token

        if self.expires_at is not None:
            expires_at = self.expires_at
            # The control plane reports UTC. Converting a naive value would instead read
            # it as local time, and west of UTC that lands the deadline hours late — the
            # tool then holds an expired credential rather than refreshing.
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            payload["Expiration"] = expires_at.astimezone(timezone.utc).isoformat()

        return payload
