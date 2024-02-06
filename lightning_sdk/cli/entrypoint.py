import os
from typing import List, Optional

from fire import Fire
from simple_term_menu import TerminalMenu

from lightning_sdk.organization import Organization
from lightning_sdk.studio import Studio
from lightning_sdk.user import User
from lightning_sdk.utils import _get_organizations_for_authed_user, _get_authed_user
from itertools import chain


class StudioCLI:
    """Command line interface (CLI) to interact with/manage Lightning AI Studios."""

    def upload(self, path: str, studio: Optional[str] = None, remote_path: Optional[str] = None) -> None:
        """Upload a file or folder to a studio.
        
        Args:
          path: The path to the file or directory you want to upload
          studio: The name of the studio to upload to. Will show a menu for selection if not specified. 
            If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME>
          remote_path: The path where the uploaded file should appear on your Studio. 
            Has to be within your Studio's home directory and will be relative to that. 
            If not specified, will use the file or directory name of the path you want to upload 
            and place it in your home directory.

        """
        if remote_path is None:
            remote_path = os.path.basename(path)

        user = _get_authed_user()
        orgs = _get_organizations_for_authed_user()

        terminal_menu = None

        possible_studios = []

        has_been_interactive = False
        if studio is None:
            has_been_interactive = True
            if not possible_studios:
                possible_studios = self._get_possible_studios(user, orgs)
            terminal_menu = self._prepare_terminal_menu_all_studios(possible_studios)
            terminal_menu.show()
            studio = terminal_menu.chosen_menu_entry

        try:
            # gracefully handle wrong name
            try:
                selected_studio = self._get_studio_from_name(user, orgs, studio)
            except InvalidNameError as e:
                if has_been_interactive:
                    raise StudioCliError(
                        f"Could not find the given Studio {studio} to upload files to. "
                        "Please contact Lightning AI directly to resolve this issue."
                    ) from e

                print(f"Could not find Studio {studio}")
                if not possible_studios:
                    possible_studios = self._get_possible_studios(user, orgs)
                terminal_menu = self._prepare_terminal_menu_all_studios(possible_studios)
                terminal_menu.show()
                studio = terminal_menu.chosen_menu_entry
                has_been_interactive = True
                selected_studio = self._get_studio_from_name(user, orgs, studio)
            except KeyboardInterrupt:
                raise KeyboardInterrupt from None

        except KeyboardInterrupt:
            raise KeyboardInterrupt from None
        
        # give user friendlier error message
        except Exception as e:  # noqa: E722
            raise StudioCliError(
                f"Could not find the given Studio {studio} to upload files to. "
                "Please contact Lightning AI directly to resolve this issue."
            ) from e

        print(f"Uploading to {selected_studio.teamspace.name}/{selected_studio.name}")
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                rel_root = os.path.relpath(root, path)
                for f in files:
                    selected_studio.upload_file(os.path.join(root, f), os.path.join(remote_path, rel_root, f))

        else:
            selected_studio.upload_file(path, remote_path=remote_path)

    def _prepare_terminal_menu_all_studios(
        self, possible_studios: List[Studio], title: Optional[str] = None
    ) -> TerminalMenu:
        if title is None:
            title = "Please select a Studio of the following studios:"

        return TerminalMenu([f"{s.teamspace.name}/{s.name}" for s in possible_studios], title=title, clear_menu_on_exit=True)

    def _get_possible_studios(self, user: User, orgs: List[Organization]) -> List[Studio]:
        Studio._skip_init = True
        teamspaces = list(user.teamspaces)
        for _org in orgs:
            teamspaces.extend(list(_org.teamspaces))

        all_studios = []

        for t in chain(user.teamspaces, *[o.teamspaces for o in orgs]):
            all_studios.extend(t.studios)

        Studio._skip_init = False

        return all_studios

    def _get_studio_from_name(self, user: User, orgs: List[Organization], name: str) -> Studio:
        try:
            teamspace, studio = name.split("/")
        except:  # noqa: E722
            raise InvalidNameError from None

        ts = user.teamspaces
        for org in orgs:
            ts.extend(org.teamspaces)

        possible_teamspaces = []
        for t in ts:
            if t.name == teamspace or t._teamspace.display_name == teamspace:
                possible_teamspaces.append(t)

        # try all teamspace-studioname combinations in case there are multiple teamspaces with that name
        # (e.g. one personal and one org teamspace)
        for t in possible_teamspaces:
            for cl in t.clusters:
                try:
                    owner_kwargs = {}
                    if isinstance(t.owner, User):
                        owner_kwargs["user"] = t.owner.name
                    else:
                        owner_kwargs["org"] = t.owner.name
                    return Studio(name=studio, teamspace=t.name, cluster=cl, **owner_kwargs)
                except:  # noqa: E722
                    continue

        raise InvalidNameError


class InvalidNameError(ValueError):
    """Exception for Invalid Teamspace/Studio Name."""


class StudioCliError(RuntimeError):
    """General Studio CLI Exception."""


def main_cli() -> None:
    """CLI entrypoint."""
    Fire(StudioCLI())

