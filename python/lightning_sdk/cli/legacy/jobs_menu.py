from typing import Dict, List, Optional

from rich.console import Console
from simple_term_menu import TerminalMenu

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.job import Job
from lightning_sdk.teamspace import Teamspace


class _JobsMenu:
    def _get_job_from_interactive_menu(self, possible_jobs: Dict[str, Job]) -> Job:
        job_ids = sorted(possible_jobs.keys())
        terminal_menu = self._prepare_terminal_menu_jobs([possible_jobs[k] for k in job_ids])
        terminal_menu.show()

        return possible_jobs[terminal_menu.chosen_menu_entry]

    def _get_job_from_name(self, job: str, possible_jobs: Dict[str, Job]) -> Job:
        for _, j in possible_jobs.items():
            if j.name == job:
                return j

        Console().print("Could not find Job {job}, please select it from the list:")
        return self._get_job_from_interactive_menu(possible_jobs)

    @staticmethod
    def _prepare_terminal_menu_jobs(possible_jobs: List[Job], title: Optional[str] = None) -> TerminalMenu:
        if title is None:
            title = "Please select a Job of the following:"

        return TerminalMenu([j.name for j in possible_jobs], title=title, clear_menu_on_exit=True)

    @staticmethod
    def _get_possible_jobs(teamspace: Teamspace) -> Dict[str, Job]:
        jobs = {}
        for j in teamspace.jobs:
            jobs[j.name] = j

        return jobs

    def _resolve_job(self, job: Optional[str], teamspace: Teamspace) -> Job:
        try:
            possible_jobs = self._get_possible_jobs(teamspace)
            if job is None:
                resolved_job = self._get_job_from_interactive_menu(possible_jobs)
            else:
                resolved_job = self._get_job_from_name(job=job, possible_jobs=possible_jobs)

            return resolved_job
        except KeyboardInterrupt:
            raise KeyboardInterrupt from None

        except Exception as e:
            raise StudioCliError(
                f"Could not find the given Job {job} in Teamspace {teamspace.name}. "
                "Please contact Lightning AI directly to resolve this issue."
            ) from e
