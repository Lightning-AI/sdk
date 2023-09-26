class Studio:
    ...

    def install(self, plugin: str):
        ...

    def run_plugin(self, name, *args, **kwargs) -> Any:
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
    def run(self, *args, **kwargs):
        ...

    def id(self, *args, **kwargs):
        ...

    def studio(self, *args, **kwargs):
        ...

class JobPlugin(Plugin):
    def run(self, *command, machine=None) -> Job:
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
    
    @property
    def stop(self):
        # stop all works and orchestrator
        ...