import concurrent.futures
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from simple_term_menu import TerminalMenu
from tqdm import tqdm

from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.cli.exceptions import StudioCliError
from lightning_sdk.cli.studios_menu import _StudiosMenu
from lightning_sdk.models import upload_model
from lightning_sdk.studio import Studio
from lightning_sdk.utils.resolve import _get_authed_user, skip_studio_init


class _Uploads(_StudiosMenu):
    """Upload files and folders to Lightning AI."""

    _studio_upload_status_path = "~/.lightning/studios/uploads"

    def model(self, name: str, path: str = ".", cloud_account: Optional[str] = None) -> None:
        """Upload a Model.

        Args:
          name: The name of the Model you want to upload.
            This should have the format <ORGANIZATION-NAME>/<TEAMSPACE-NAME>/<MODEL-NAME>.
          path: The path to the file or directory you want to upload. Defaults to the current directory.
          cloud_account: The name of the cloud account to store the Model in.
        """
        upload_model(name, path, cloud_account=cloud_account)

    def _resolve_studio(self, studio: Optional[str]) -> Studio:
        user = _get_authed_user()
        possible_studios = self._get_possible_studios(user)

        try:
            if studio is None:
                selected_studio = self._get_studio_from_interactive_menu(possible_studios)
            else:
                selected_studio = self._get_studio_from_name(studio, possible_studios)

        except KeyboardInterrupt:
            raise KeyboardInterrupt from None

        # give user friendlier error message
        except Exception as e:
            raise StudioCliError(
                f"Could not find the given Studio {studio} to upload files to. "
                "Please contact Lightning AI directly to resolve this issue."
            ) from e

        with skip_studio_init():
            return Studio(**selected_studio)

    def folder(self, path: str, studio: Optional[str] = None, remote_path: Optional[str] = None) -> None:
        """Upload a file or folder to a Studio.

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

        if not Path(path).exists():
            raise FileNotFoundError(f"The provided path does not exist: {path}.")
        if not Path(path).is_dir():
            raise StudioCliError(f"The provided path is not a folder: {path}. Use `lightning upload file` instead.")

        selected_studio = self._resolve_studio(studio)

        print(f"Uploading to {selected_studio.teamspace.name}/{selected_studio.name}")

        pairs = {}
        for root, _, files in os.walk(path):
            rel_root = os.path.relpath(root, path)
            for f in files:
                pairs[os.path.join(root, f)] = os.path.join(remote_path, rel_root, f)

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

        studio_url = (
            _get_cloud_url().replace(":443", "")
            + "/"
            + selected_studio.owner.name
            + "/"
            + selected_studio.teamspace.name
            + "/studios/"
            + selected_studio.name
        )
        print(f"See your files at {studio_url}")

    def file(self, path: str, studio: Optional[str] = None, remote_path: Optional[str] = None) -> None:
        """Upload a file to a Studio.

        Args:
          path: The path to the file you want to upload
          studio: The name of the studio to upload to. Will show a menu for selection if not specified.
            If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME>
          remote_path: The path where the uploaded file should appear on your Studio.
            Has to be within your Studio's home directory and will be relative to that.
            If not specified, will use the name of the file you want to upload
            and place it in your home directory.
        """
        if remote_path is None:
            remote_path = os.path.basename(path)

        if Path(path).is_dir():
            raise StudioCliError(f"The provided path is a folder: {path}. Use `lightning upload folder` instead.")
        if not Path(path).exists():
            raise FileNotFoundError(f"The provided path does not exist: {path}.")

        selected_studio = self._resolve_studio(studio)

        print(f"Uploading to {selected_studio.teamspace.name}/{selected_studio.name}")

        self._single_file_upload(selected_studio, path, remote_path, True)

        studio_url = (
            _get_cloud_url().replace(":443", "")
            + "/"
            + selected_studio.owner.name
            + "/"
            + selected_studio.teamspace.name
            + "/studios/"
            + selected_studio.name
        )
        print(f"See your file at {studio_url}")

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

    def _dump_current_upload_state(self, studio: Studio, remote_path: str, state_dict: Dict[str, str]) -> None:
        """Dumps the current upload state so that we can safely resume later."""
        curr_path = os.path.abspath(
            os.path.expandvars(
                os.path.expanduser(
                    os.path.join(self._studio_upload_status_path, studio._studio.id, remote_path + ".json")
                )
            )
        )

        dirpath = os.path.dirname(curr_path)
        if state_dict:
            os.makedirs(os.path.dirname(curr_path), exist_ok=True)
            with open(curr_path, "w") as f:
                json.dump(state_dict, f, indent=4)
            return

        if os.path.exists(curr_path):
            os.remove(curr_path)
        if os.path.exists(dirpath):
            os.removedirs(dirpath)

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
