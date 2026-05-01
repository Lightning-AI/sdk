import os
from contextlib import suppress
from typing import Dict, List, Optional, Union

import click
from simple_term_menu import TerminalMenu

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.studio import VM, Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.resolve import _get_authed_user


class StudiosMenu:
    """This class is used to select a studio from a list of possible studios within a teamspace.

    It can be used to select a studio from a list of possible studios, or to resolve a studio from a name.
    """

    def __init__(self, teamspace: Teamspace, vm: bool = False) -> None:
        """Initialize the StudiosMenu with a teamspace.

        Args:
            teamspace: The teamspace to list studios from
        """
        self.teamspace = teamspace
        self.vm = vm

    def _get_studio_from_interactive_menu(self, possible_studios: Dict[str, Union[Studio, VM]]) -> Union[Studio, VM]:
        studio_names = sorted(possible_studios.keys())
        terminal_menu = self._prepare_terminal_menu_studios(studio_names, vm=self.vm)
        terminal_menu.show()

        selected_name = studio_names[terminal_menu.chosen_menu_index]
        return possible_studios[selected_name]

    def _get_studio_from_name(self, studio: str, possible_studios: Dict[str, Union[Studio, VM]]) -> Union[Studio, VM]:
        if studio in possible_studios:
            return possible_studios[studio]

        click.echo(f"Could not find {'VM' if self.vm else 'Studio'} {studio}, please select it from the list:")
        return self._get_studio_from_interactive_menu(possible_studios)

    @staticmethod
    def _prepare_terminal_menu_studios(
        studio_names: List[str], title: Optional[str] = None, vm: bool = False
    ) -> TerminalMenu:
        if title is None:
            title = f"Please select a {'VM' if vm else 'Studio'} out of the following:"

        return TerminalMenu(studio_names, title=title, clear_menu_on_exit=True)

    def _get_possible_studios(self) -> Dict[str, Union[Studio, VM]]:
        """Get all available studios in the teamspace."""
        studios: Dict[str, Union[Studio, VM]] = {}

        user = _get_authed_user()
        teamspace_studios = self.teamspace.vms if self.vm else self.teamspace.studios
        for studio in teamspace_studios:
            if studio._studio.user_id == user.id:
                studios[studio.name] = studio
        return studios

    def __call__(self, studio: Optional[str] = None) -> Union[Studio, VM]:
        """Select a studio from the teamspace.

        Args:
            studio: Optional studio name to select. If not provided, will show interactive menu.

        Returns:
            Selected Studio/VM object

        Raises:
            StudioCliError: If studio selection fails
        """
        try:
            # try to resolve the studio from the name, environment or config
            resolved_studio = None

            selected_cls = VM if self.vm else Studio

            with suppress(Exception):
                resolved_studio = selected_cls(name=studio, teamspace=self.teamspace, create_ok=False)

            if resolved_studio is not None:
                return resolved_studio

            if os.environ.get("LIGHTNING_NON_INTERACTIVE", "0") == "1" and studio is None:
                raise ValueError(
                    f"{'VM' if self.vm else 'Studio'} selection is not supported in non-interactive mode. "
                    "Please provide a studio name."
                )

            click.echo(f"Listing studios in teamspace {self.teamspace.owner.name}/{self.teamspace.name}...")

            possible_studios = self._get_possible_studios()

            if not possible_studios:
                raise ValueError(f"No studios found in teamspace {self.teamspace.name}")

            if studio is None:
                return self._get_studio_from_interactive_menu(possible_studios)

            return self._get_studio_from_name(studio, possible_studios)

        except KeyboardInterrupt:
            raise KeyboardInterrupt from None

        except Exception as e:
            raise StudioCliError(
                f"Could not resolve a {'VM' if self.vm else 'Studio'}. "
                "Please pass it as an argument or contact Lightning AI directly to resolve this issue."
            ) from e
