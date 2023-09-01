from typing import List

from lightning_sdk.status import Status


class Work:
    def __init__(self) -> None:
        ...

    @property
    def status(self) -> Status:
        ...


class Job:
    def __init__(
        self,
        name: str,
    ) -> None:
        self._name = name

    @property
    def status(self) -> Status:
        ...

    @property
    def works(self) -> List[Work]:
        ...
