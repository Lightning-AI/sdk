from typing import Any, List, Optional


class Studio:
    """"""

    ...

    def install(self, plugin: str) -> None:
        """"""
        ...

    def run_plugin(self, name, *args, **kwargs) -> Any:
        """"""
        ...

    @property
    def installed_plugins(self) -> List[Plugin]:
        ...

    @property
    def available_plugins(self) -> List[Plugin]:
        ...

    def plugin(self, name: str) -> Plugin:
        ...


class Plugin:
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """"""
        ...

    @property
    def id(self) -> str:
        """"""
        ...

    def studio(self) -> Studio:
        """"""
        ...


class JobPlugin(Plugin):
    # TODO: make machine an actual machine type
    def run(self, *commands: str, machine: Optional[str] = None) -> Job:
        """"""
        ...


class Job:
    """"""

    def __init__(
        self,
        name: str,
    ) -> None:
        self._name = name

    @property
    def status(self) -> Status:
        """"""
        ...

    @property
    def works(self) -> List[Work]:
        """"""
        ...

    @property
    def stop(self):
        """"""
        # stop all works and orchestrator
        ...
