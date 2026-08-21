# This file is vendored.
# Do not edit it directly; changes will be overwritten.
# Make changes in the internal upstream repository instead.

import os
from pathlib import Path
from typing import Optional


def truthy(val) -> bool:
    if val in [
            "1",
            "true",
            "True",
            True,
    ]:
        return True
    if val in ["0", "false", "False", False, None]:
        return False

    return bool(val)


def _float_env(name: str, default: Optional[float]) -> Optional[float]:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


LIGHTNING_CLOUD_URL = os.getenv("LIGHTNING_CLOUD_URL", "https://lightning.ai")

# Default per-request timeouts, in seconds. See rest_client.create_swagger_client.
LIGHTNING_CLOUD_CONNECT_TIMEOUT = _float_env("LIGHTNING_CLOUD_CONNECT_TIMEOUT", 10.0)
LIGHTNING_CLOUD_READ_TIMEOUT = _float_env("LIGHTNING_CLOUD_READ_TIMEOUT", 30.0)

SSL_CA_CERT = os.getenv("REQUESTS_CA_BUNDLE",
                        default=os.getenv("SSL_CERT_FILE", default=None))
VERSION = os.getenv("VERSION", "0.0.1")
DEBUG = truthy(os.getenv("DEBUG"))
CONTEXT = os.getenv("CONTEXT", "staging-3")
LIGHTNING_SETTINGS_PATH = os.getenv(
    'LIGHTNING_SETTINGS_PATH',
    str(Path.home() / '.lightning' / 'settings.json'))
LIGHTNING_CREDENTIAL_PATH = os.getenv(
    'LIGHTNING_CREDENTIAL_PATH',
    str(Path.home() / '.lightning' / 'credentials.json'))

DOT_IGNORE_FILENAME = ".lightningignore"

LEEWAY = 100
IS_DEV_ENV = True
LIGHTNING_CLOUD_PROJECT_ID = os.getenv("LIGHTNING_CLOUD_PROJECT_ID")


def reset_global_variables() -> None:
    """ Reset the settings from env variables"""
    global DEBUG, CONTEXT, LIGHTNING_CLOUD_URL

    if 'DEBUG' in os.environ:
        DEBUG = truthy(os.environ['DEBUG'])

    if 'GRID_CLUSTER_ID' in os.environ:
        CONTEXT = os.environ['GRID_CLUSTER_ID']

    if 'GRID_URL' in os.environ:
        LIGHTNING_CLOUD_URL = os.environ['GRID_URL']
