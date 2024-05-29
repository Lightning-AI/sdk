from lightning_sdk.helpers import _check_version_and_prompt_upgrade
from lightning_sdk.job import Job
from lightning_sdk.machine import Machine
from lightning_sdk.organization import Organization
from lightning_sdk.plugin import JobsPlugin, MultiMachineTrainingPlugin, Plugin, SlurmJobsPlugin
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User

__all__ = [
    "Job",
    "JobsPlugin",
    "Machine",
    "MultiMachineTrainingPlugin",
    "Organization",
    "Plugin",
    "SlurmJobsPlugin",
    "Status",
    "Studio",
    "Teamspace",
    "User",
]

__version__ = "0.1.9"
_check_version_and_prompt_upgrade(__version__)
