from enum import Enum
from typing import List, Optional

from lightning.app.utilities.network import LightningClient

from lightning_sdk.status import Status


class Work:
    def __init__(self):
        ...

    @property
    def status(self) -> Status:
        ...


class Job:
    def __init__(
        self,
        name: str,
    ):
        self._name = name

    @property
    def status(self) -> Status:
        ...

    @property
    def works(self) -> List[Work]:
        ...
