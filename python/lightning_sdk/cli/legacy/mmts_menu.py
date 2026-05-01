from typing import Dict, List, Optional

from rich.console import Console
from simple_term_menu import TerminalMenu

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.mmt import MMT
from lightning_sdk.teamspace import Teamspace


class _MMTsMenu:
    def _get_mmt_from_interactive_menu(self, possible_mmts: Dict[str, MMT]) -> MMT:
        job_ids = sorted(possible_mmts.keys())
        terminal_menu = self._prepare_terminal_menu_mmts([possible_mmts[k] for k in job_ids])
        terminal_menu.show()

        return possible_mmts[terminal_menu.chosen_menu_entry]

    def _get_mmt_from_name(self, mmt: str, possible_mmts: Dict[str, MMT]) -> MMT:
        for _, j in possible_mmts.items():
            if j.name == mmt:
                return j

        Console().print(f"Could not find Multi-Machine Job {mmt}, please select it from the list:")
        return self._get_mmt_from_interactive_menu(possible_mmts)

    @staticmethod
    def _prepare_terminal_menu_mmts(possible_mmts: List[MMT], title: Optional[str] = None) -> TerminalMenu:
        if title is None:
            title = "Please select a Multi-Machine Job of the following:"

        return TerminalMenu([m.name for m in possible_mmts], title=title, clear_menu_on_exit=True)

    @staticmethod
    def _get_possible_mmts(teamspace: Teamspace) -> Dict[str, MMT]:
        jobs = {}
        for j in teamspace.multi_machine_jobs:
            jobs[j.name] = j

        return jobs

    def _resolve_mmt(self, mmt: Optional[str], teamspace: Teamspace) -> MMT:
        try:
            possible_mmts = self._get_possible_mmts(teamspace)
            if mmt is None:
                resolved_mmt = self._get_mmt_from_interactive_menu(possible_mmts)
            else:
                resolved_mmt = self._get_mmt_from_name(mmt=mmt, possible_mmts=possible_mmts)

            return resolved_mmt
        except KeyboardInterrupt:
            raise KeyboardInterrupt from None

        except Exception as e:
            raise StudioCliError(
                f"Could not find the given Multi-Machine-Job {mmt} in Teamspace {teamspace.name}. "
                "Please contact Lightning AI directly to resolve this issue."
            ) from e
