import os
from contextlib import suppress
from typing import Dict, List, Optional

import click
from simple_term_menu import TerminalMenu

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.resolve import _get_authed_user


class StudiosMenu:
    """This class is used to select a studio from a list of possible studios within a teamspace.

    It can be used to select a studio from a list of possible studios, or to resolve a studio from a name.
    """

    def __init__(self, teamspace: Teamspace) -> None:
        """Initialize the StudiosMenu with a teamspace.

        Args:
            teamspace: The teamspace to list studios from
        """
        self.teamspace = teamspace

    def _get_studio_from_interactive_menu(self, possible_studios: Dict[str, Studio]) -> Studio:
        studio_names = sorted(possible_studios.keys())
        terminal_menu = self._prepare_terminal_menu_studios(studio_names)
        terminal_menu.show()

        selected_name = studio_names[terminal_menu.chosen_menu_index]
        return possible_studios[selected_name]

    def _get_studio_from_name(self, studio: str, possible_studios: Dict[str, Studio]) -> Studio:
        if studio in possible_studios:
            return possible_studios[studio]

        click.echo(f"Could not find Studio {studio}, please select it from the list:")
        return self._get_studio_from_interactive_menu(possible_studios)

    @staticmethod
    def _prepare_terminal_menu_studios(studio_names: List[str], title: Optional[str] = None) -> TerminalMenu:
        if title is None:
            title = "Please select a Studio out of the following:"

        return TerminalMenu(studio_names, title=title, clear_menu_on_exit=True)

    def _get_possible_studios(self) -> Dict[str, Studio]:
        """Get all available studios in the teamspace."""
        studios = {}

        user = _get_authed_user()
        for studio in self.teamspace.studios:
            if studio._studio.user_id == user.id:
                studios[studio.name] = studio
        return studios

    def __call__(self, studio: Optional[str] = None) -> Studio:
        """Select a studio from the teamspace.

        Args:
            studio: Optional studio name to select. If not provided, will show interactive menu.

        Returns:
            Selected Studio object

        Raises:
            StudioCliError: If studio selection fails
        """
        try:
            # try to resolve the studio from the name, environment or config
            resolved_studio = None

            with suppress(Exception):
                resolved_studio = Studio(name=studio, teamspace=self.teamspace, create_ok=False)

            if resolved_studio is not None:
                return resolved_studio

            if os.environ.get("LIGHTNING_NON_INTERACTIVE", "0") == "1" and studio is None:
                raise ValueError(
                    "Studio selection is not supported in non-interactive mode. Please provide a studio name."
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
                "Could not resolve a Studio. "
                "Please pass it as an argument or contact Lightning AI directly to resolve this issue."
            ) from e
