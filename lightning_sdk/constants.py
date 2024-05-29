import os
from collections import defaultdict
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


def fn() -> str:
    return str(uuid4().hex)


__GLOBAL_LIGHTNING_RUN_IDS_STORE__ = defaultdict(fn)
