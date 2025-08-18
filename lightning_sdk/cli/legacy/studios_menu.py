from typing import Dict, List, Optional

from rich.console import Console
from simple_term_menu import TerminalMenu

from lightning_sdk import Studio
from lightning_sdk.api import OrgApi, TeamspaceApi
from lightning_sdk.user import User


class _StudiosMenu:
    def _get_studio_from_interactive_menu(self, possible_studios: List[Dict[str, str]]) -> Dict[str, str]:
        terminal_menu = self._prepare_terminal_menu_list_studios(possible_studios)
        terminal_menu.show()
        return possible_studios[terminal_menu.chosen_menu_index]

    def _get_studio_from_name(self, studio: str, possible_studios: List[Dict[str, str]]) -> Dict[str, str]:
        teamspace, name = studio.split("/", maxsplit=1)
        for st in possible_studios:
            if st["teamspace"] == teamspace and name == st["name"]:
                return st

        Console().print("Could not find Studio {studio}, please select it from the list:")
        return self._get_studio_from_interactive_menu(possible_studios)

    @staticmethod
    def _prepare_terminal_menu_list_studios(
        possible_studios: List[Dict[str, str]], title: Optional[str] = None
    ) -> TerminalMenu:
        if title is None:
            title = "Please select a Studio of the following studios:"

        return TerminalMenu(
            [f"{s['teamspace']}/{s['name']}" for s in possible_studios], title=title, clear_menu_on_exit=True
        )

    @staticmethod
    def _get_possible_studios(user: User, is_owner: bool = True) -> List[Dict[str, str]]:
        teamspace_api = TeamspaceApi()
        org_api = OrgApi()
        user_api = user._user_api
        possible_studios = []

        user_api._get_organizations_for_authed_user()
        memberships = user_api._get_all_teamspace_memberships(user_id=user.id)

        teamspaces = {}
        # get all teamspace memberships
        for membership in memberships:
            teamspace_id = membership.project_id

            if is_owner:
                # get all studios for teamspace when user is owner
                all_studios = user._user_api._get_cloudspaces_for_user(user_id=user.id, project_id=teamspace_id)
            else:
                all_studios = user._user_api._get_cloudspaces_for_user(project_id=teamspace_id)

            for st in all_studios:
                # populate teamspace info if necessary
                if teamspace_id not in teamspaces:
                    ts = teamspace_api._get_teamspace_by_id(teamspace_id)
                    ts_name = ts.name

                    # get organization if necessary
                    if ts.owner_type == "organization":
                        org_name = org_api._get_org_by_id(ts.owner_id).name
                        user_name = None
                    else:
                        org_name = None

                        # don't do a request if not necessary
                        if ts.owner_id == user.id:
                            user_name = user.name
                        else:
                            user_name = user_api._get_user_by_id(ts.owner_id).username

                    teamspaces[teamspace_id] = {"user": user_name, "org": org_name, "teamspace": ts_name}
                possible_studios.append({"name": st.name, **teamspaces[teamspace_id]})

        return possible_studios

    def _get_studio(self, name: str, teamspace: str) -> Studio:
        """Get studio object from name and teamspace.

        Args:
            name: Name of the studio
            teamspace: Name of the teamspace
        """
        if teamspace:
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
        return studio
