import os
from uuid import uuid4

_LIGHTNING_DEBUG = {
    "": False,
    "0": False,
    "false": False,
    "no": False,
    "1": True,
    "true": True,
    "yes": True,
}.get(os.getenv("LIGHTNING_DEBUG", "").lower(), False)

# The LightningRunId is created globally to be available across all processes and threads
__GLOBAL_LIGHTNING_RUN_ID__ = str(uuid4().hex)
