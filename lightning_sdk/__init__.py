from lightning_sdk.agents import Agent
from lightning_sdk.ai_hub import AIHub
from lightning_sdk.constants import __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__  # noqa: F401
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
    "Agent",
    "AIHub",
]

__version__ = "0.1.45"
_check_version_and_prompt_upgrade(__version__)
