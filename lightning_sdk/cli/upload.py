import concurrent.futures
import json
import os
from itertools import chain
from typing import Dict, List, Optional

from simple_term_menu import TerminalMenu
from tqdm import tqdm

from lightning_sdk.cli.exceptions import InvalidNameError, StudioCliError
from lightning_sdk.organization import Organization
from lightning_sdk.studio import Studio
from lightning_sdk.user import User
from lightning_sdk.utils import _get_authed_user, _get_organizations_for_authed_user


class _Uploads:
    _studio_upload_status_path = "~/.lightning/studios/uploads"

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
        except Exception as e:
            raise StudioCliError(
                f"Could not find the given Studio {studio} to upload files to. "
                "Please contact Lightning AI directly to resolve this issue."
            ) from e

        print(f"Uploading to {selected_studio.teamspace.name}/{selected_studio.name}")
        pairs = {}
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                rel_root = os.path.relpath(root, path)
                for f in files:
                    pairs[os.path.join(root, f)] = os.path.join(remote_path, rel_root, f)

        else:
            pairs[path] = remote_path

        upload_state = self._resolve_previous_upload_state(selected_studio, remote_path, pairs)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = self._start_parallel_upload(executor, selected_studio, upload_state)

            update_fn = (
                tqdm(total=len(upload_state)).update if self._global_upload_progress(upload_state) else lambda x: None
            )

            for f in concurrent.futures.as_completed(futures):
                upload_state.pop(f.result())
                self._dump_current_upload_state(selected_studio, remote_path, upload_state)
                update_fn(1)

    def _start_parallel_upload(
        self, executor: concurrent.futures.ThreadPoolExecutor, studio: Studio, upload_state: Dict[str, str]
    ) -> List[concurrent.futures.Future]:
        # only add progress bar on individual uploads with less than 10 files
        progress_bar = not self._global_upload_progress(upload_state)

        futures = []
        for k, v in upload_state.items():
            futures.append(
                executor.submit(
                    self._single_file_upload, studio=studio, local_path=k, remote_path=v, progress_bar=progress_bar
                )
            )

        return futures

    def _single_file_upload(self, studio: Studio, local_path: str, remote_path: str, progress_bar: bool) -> str:
        studio.upload_file(local_path, remote_path, progress_bar)
        return local_path

    def _prepare_terminal_menu_all_studios(
        self, possible_studios: List[Studio], title: Optional[str] = None
    ) -> TerminalMenu:
        if title is None:
            title = "Please select a Studio of the following studios:"

        return TerminalMenu(
            [f"{s.teamspace.name}/{s.name}" for s in possible_studios], title=title, clear_menu_on_exit=True
        )

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

    def _dump_current_upload_state(self, studio: Studio, remote_path: str, state_dict: Dict[str, str]) -> None:
        """Dumps the current upload state so that we can safely resume later."""
        curr_path = os.path.abspath(
            os.path.expandvars(
                os.path.expanduser(
                    os.path.join(self._studio_upload_status_path, studio._studio.id, remote_path + ".json")
                )
            )
        )
        if state_dict:
            os.makedirs(os.path.dirname(curr_path), exist_ok=True)
            with open(curr_path, "w") as f:
                json.dump(state_dict, f, indent=4)
            return

        os.remove(curr_path)
        os.removedirs(os.path.dirname(curr_path))

    def _resolve_previous_upload_state(
        self, studio: Studio, remote_path: str, state_dict: Dict[str, str]
    ) -> Dict[str, str]:
        """Resolves potential previous uploads to continue if possible."""
        curr_path = os.path.abspath(
            os.path.expandvars(
                os.path.expanduser(
                    os.path.join(self._studio_upload_status_path, studio._studio.id, remote_path + ".json")
                )
            )
        )

        # no previous download exists
        if not os.path.isfile(curr_path):
            return state_dict

        menu = TerminalMenu(
            [
                "no, I accept that this may cause overwriting existing files",
                "yes, continue previous upload",
            ],
            title=f"Found an incomplete upload for {studio.teamspace.name}/{studio.name}:{remote_path}. "
            "Should we resume the previous upload?",
        )
        index = menu.show()
        if index == 0:  # selected to start new upload
            return state_dict

        # at this point we know we want to resume the previous upload
        with open(curr_path) as f:
            return json.load(f)

    def _global_upload_progress(self, upload_state: Dict[str, str]) -> bool:
        return len(upload_state) > 10
