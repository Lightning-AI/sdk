import os
from contextlib import suppress
from typing import Dict, List, Optional

import click
from simple_term_menu import TerminalMenu

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.utils.resolve import resolve_teamspace_owner_name_format
from lightning_sdk.teamspace import Organization, Teamspace
from lightning_sdk.user import Owner, User
from lightning_sdk.utils.resolve import ApiException, _get_authed_user, _resolve_teamspace


class TeamspacesMenu:
    """This class is used to select a teamspace from a list of possible teamspaces.

    It can be used to select a teamspace from a list of possible teamspaces, or to resolve a teamspace from a name.
    """

    def __init__(self, owner: Optional[Owner] = None) -> None:
        self._owner: Owner = owner

    def _get_teamspace_from_interactive_menu(self, possible_teamspaces: Dict[str, str]) -> str:
        teamspace_ids = sorted(possible_teamspaces.keys())
        terminal_menu = self._prepare_terminal_menu_teamspaces(
            [possible_teamspaces[k] for k in teamspace_ids], self._owner
        )
        terminal_menu.show()

        selected_id = teamspace_ids[terminal_menu.chosen_menu_index]
        return possible_teamspaces[selected_id]

    def _get_teamspace_from_name(self, teamspace: str, possible_teamspaces: Dict[str, str]) -> str:
        for _, ts in possible_teamspaces.items():
            if ts == teamspace:
                return ts

        click.echo(f"Could not find Teamspace {self._owner.name}/{teamspace}, please select it from the list:")
        return self._get_teamspace_from_interactive_menu(possible_teamspaces)

    @staticmethod
    def _prepare_terminal_menu_teamspaces(
        possible_teamspaces: List[str],
        owner: Owner,
        title: Optional[str] = None,
    ) -> TerminalMenu:
        if title is None:
            title = f"Please select a Teamspace (owned by {owner.name}) out of the following:"

        return TerminalMenu(possible_teamspaces, title=title, clear_menu_on_exit=True)

    def _get_possible_teamspaces(self, user: User) -> Dict[str, str]:
        user_api = user._user_api

        memberships = user_api._get_all_teamspace_memberships(
            user_id=user.id, org_id=self._owner.id if isinstance(self._owner, Organization) else None
        )

        teamspaces = {}
        # get all teamspace memberships
        for membership in memberships:
            teamspace_id = membership.project_id
            teamspace_name = membership.name

            if membership.owner_id == self._owner.id:
                teamspaces[teamspace_id] = teamspace_name

        return teamspaces

    def __call__(self, teamspace: Optional[str] = None) -> Teamspace:
        resolved_teamspace = None
        resolved_teamspace = resolve_teamspace_owner_name_format(teamspace)
        if resolved_teamspace is not None:
            return resolved_teamspace

        if self._owner is None:
            # resolve owner if required
            from lightning_sdk.cli.utils.owner_selection import OwnerMenu

            menu = OwnerMenu()
            self._owner = menu()

        if isinstance(self._owner, Organization):
            org = self._owner
            user = None
        elif isinstance(self._owner, User):
            org = None
            user = self._owner

        with suppress(ApiException, ValueError, RuntimeError):
            resolved_teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)

        if resolved_teamspace is not None:
            return resolved_teamspace

        if os.environ.get("LIGHTNING_NON_INTERACTIVE", "0") == "1":
            raise ValueError(
                "Teamspace selection is not supported in non-interactive mode. "
                "Please provide a teamspace name in the format of 'owner/teamspace'."
            )

        # if the teamspace is not resolved, try to get the teamspace from the interactive menu
        # this could mean that either no teamspace was provided or the provided teamspace is not valid
        try:
            auth_user = _get_authed_user()

            possible_teamspaces = self._get_possible_teamspaces(auth_user)
            if teamspace is None:
                teamspace_name = self._get_teamspace_from_interactive_menu(possible_teamspaces=possible_teamspaces)
            else:
                teamspace_name = self._get_teamspace_from_name(
                    teamspace=teamspace, possible_teamspaces=possible_teamspaces
                )

            return Teamspace(teamspace_name, org=org, user=user)

        except KeyboardInterrupt:
            raise KeyboardInterrupt from None

        except Exception as e:
            raise StudioCliError(
                f"Could not find the given Teamspace owned by {self._owner.name}. "
                "Please contact Lightning AI directly to resolve this issue."
            ) from e
