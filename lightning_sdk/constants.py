import os

_LIGHTNING_DEBUG = {
    "": False,
    "0": False,
    "false": False,
    "no": False,
    "1": True,
    "true": True,
    "yes": True,
}.get(os.getenv("LIGHTNING_DEBUG", "").lower(), False)
