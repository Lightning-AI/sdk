from typing import Optional

from lightning_sdk import Machine, Studio


class _Start:
    """Start resources on the Lightning AI platform."""

    def __init__(self) -> None:
        _machine_values = tuple([machine.name for machine in Machine.__dict__.values() if isinstance(machine, Machine)])

        docstr_studio = f"""Start a studio on a given machine.

        Args:
            name: The name of the studio to start.
                If not specified, tries to infer from the environment (e.g. when run from within a Studio.)
            teamspace: The teamspace the studio is part of. Should be of format <OWNER>/<TEAMSPACE_NAME>.
                If not specified, tries to infer from the environment (e.g. when run from within a Studio.)
            machine: The machine type to start the studio on. One of {", ".join(_machine_values)}.
                Defaults to the CPU Machine.
        """
        self.studio.__func__.__doc__ = docstr_studio

    def studio(self, name: Optional[str] = None, teamspace: Optional[str] = None, machine: str = "CPU") -> None:
        if teamspace is not None:
            ts_splits = teamspace.split("/")
            if len(ts_splits) != 2:
                raise ValueError(f"Teamspace should be of format <OWNER>/<TEAMSPACE_NAME> but got {teamspace}")
            owner, teamspace = ts_splits
        else:
            owner, teamspace = None, None

        try:
            studio = Studio(name=name, teamspace=teamspace, org=owner, user=None, create_ok=False)
        except (RuntimeError, ValueError):
            studio = Studio(name=name, teamspace=teamspace, org=None, user=owner, create_ok=False)

        try:
            resolved_machine = getattr(Machine, machine.upper(), Machine(machine, machine))
        except KeyError:
            resolved_machine = machine

        studio.start(resolved_machine)
