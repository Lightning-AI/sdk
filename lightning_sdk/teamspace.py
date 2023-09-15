from typing import List, Optional
from lightning_sdk.studio import Studio


class Teamspace:
    def __init__(
        self,
        name: Optional[str] = None,
        org: Optional[str] = None,
    ) -> None:
        self._name: Optional[str] = name
        self._org: Optional[str] = org
        self._id: Optional[str] = None  # This is the only thing that is important upon initialization

    @property
    def id(self) -> str:
        return self._id

    def studio(self, name: Optional[str] = None) -> Studio:
        return Studio(name=name, teamspace=self._name, org=self._org)
