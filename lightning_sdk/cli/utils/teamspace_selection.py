import os
from typing import Dict, List, Optional

import click
from simple_term_menu import TerminalMenu

from lightning_sdk.api import OrgApi
from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.utils.resolve import resolve_teamspace_owner_name_format
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _get_authed_user


class TeamspacesMenu:
    """This class is used to select a teamspace from a list of possible teamspaces.

    It can be used to select a teamspace from a list of possible teamspaces, or to resolve a teamspace from a name.
    """

    def _get_teamspace_from_interactive_menu(self, possible_teamspaces: Dict[str, Dict[str, str]]) -> Dict[str, str]:
        teamspace_ids = sorted(possible_teamspaces.keys())
        terminal_menu = self._prepare_terminal_menu_teamspaces([possible_teamspaces[k] for k in teamspace_ids])
        terminal_menu.show()

        selected_id = teamspace_ids[terminal_menu.chosen_menu_index]
        return possible_teamspaces[selected_id]

    def _get_teamspace_from_name(
        self, teamspace: str, possible_teamspaces: Dict[str, Dict[str, str]]
    ) -> Dict[str, str]:
        try:
            owner, name = teamspace.split("/", maxsplit=1)
        except ValueError as e:
            raise ValueError(
                f"Invalid teamspace format: '{teamspace}'. "
                "Teamspace should be specified as '{teamspace_owner}/{teamspace_name}' "
                "(e.g., 'my-org/my-teamspace')."
            ) from e

        for _, ts in possible_teamspaces.items():
            if ts["name"] == name and (ts["user"] == owner or ts["org"] == owner):
                return ts

        click.echo(f"Could not find Teamspace {teamspace}, please select it from the list:")
        return self._get_teamspace_from_interactive_menu(possible_teamspaces)

    @staticmethod
    def _prepare_terminal_menu_teamspaces(
        possible_teamspaces: List[Dict[str, str]], title: Optional[str] = None
    ) -> TerminalMenu:
        if title is None:
            title = "Please select a Teamspace out of the following:"

        return TerminalMenu(
            [f"{t['user'] or t['org']}/{t['name']}" for t in possible_teamspaces], title=title, clear_menu_on_exit=True
        )

    @staticmethod
    def _get_possible_teamspaces(user: User) -> Dict[str, Dict[str, str]]:
        org_api = OrgApi()
        user_api = user._user_api

        user_api._get_organizations_for_authed_user()
        memberships = user_api._get_all_teamspace_memberships(user_id=user.id)

        teamspaces = {}
        # get all teamspace memberships
        for membership in memberships:
            teamspace_id = membership.project_id
            teamspace_name = membership.name

            # get organization if necessary
            if membership.owner_type == "organization":
                org_name = org_api._get_org_by_id(membership.owner_id).name
                user_name = None
            else:
                org_name = None

                # don't do a request if not necessary
                if membership.owner_id == user.id:
                    user_name = user.name
                else:
                    user_name = user_api._get_user_by_id(membership.owner_id).username

            teamspaces[teamspace_id] = {"user": user_name, "org": org_name, "name": teamspace_name}

        return teamspaces

    def __call__(self, teamspace: Optional[str] = None) -> Teamspace:
        try:
            # try to resolve the teamspace from the name, environment or config
            resolved_teamspace = resolve_teamspace_owner_name_format(teamspace)

            if resolved_teamspace is not None:
                return resolved_teamspace

            if os.environ.get("LIGHTNING_NON_INTERACTIVE", "0") == "1":
                raise ValueError(
                    "Teamspace selection is not supported in non-interactive mode. "
                    "Please provide a teamspace name in the format of 'owner/teamspace'."
                )

            # if the teamspace is not resolved, try to get the teamspace from the interactive menu
            # this could mean that either no teamspace was provided or the provided teamspace is not valid
            user = _get_authed_user()

            possible_teamspaces = self._get_possible_teamspaces(user)
            if teamspace is None:
                teamspace = resolve_teamspace_owner_name_format(teamspace)
                teamspace_dict = self._get_teamspace_from_interactive_menu(possible_teamspaces=possible_teamspaces)
            else:
                teamspace_dict = self._get_teamspace_from_name(
                    teamspace=teamspace, possible_teamspaces=possible_teamspaces
                )

            return Teamspace(**teamspace_dict)
        except KeyboardInterrupt:
            raise KeyboardInterrupt from None

        except Exception as e:
            raise StudioCliError(
                f"Could not find the given Teamspace {teamspace}. "
                "Please contact Lightning AI directly to resolve this issue."
            ) from e
