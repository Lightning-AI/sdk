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


class Store:
    def __init__(self) -> None:
        self._d = {}
        # This is needed to ensure the ids are the same within created threads and processes.
        self._list = [str(uuid4().hex) for _ in range(500)]

    def __getitem__(self, key: str) -> str:
        """Get item."""
        if key in self._d:
            return self._d[key]

        value = self._list.pop(0) if self._list else str(uuid4().hex)
        self._d[key] = value
        return value


__GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__ = Store()
