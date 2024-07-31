import os
from pathlib import Path
from typing import Optional

from lightning_sdk.cli.exceptions import StudioCliError
from lightning_sdk.cli.studios_menu import _StudiosMenu
from lightning_sdk.studio import Studio
from lightning_sdk.utils import _get_authed_user, skip_studio_init


class _Downloads(_StudiosMenu):
    def download(self, path: str = "", studio: Optional[str] = None, local_path: str = ".") -> None:
        """Download a file or folder from a studio.

        Args:
          path: The relative path within the Studio you want to download.
            If you leave it empty it will download whole studio and locally creates a new folder
            with the same name as the selected studio.
          studio: The name of the studio to upload to. Will show a menu for selection if not specified.
            If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME>
          local_path: The path to the directory you want to download files or folders

        """
        local_path = Path(local_path)
        if not local_path.is_dir():
            raise NotADirectoryError(f"'{local_path}' is not a directory")
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
            studio = Studio(**selected_studio)
        if not path:
            local_path /= studio.name
            path = ""
        try:
            if not path:
                raise FileNotFoundError()
            studio.download_file(remote_path=path, file_path=str(local_path / os.path.basename(path)))
        except Exception:
            try:
                studio.download_folder(remote_path=path, target_path=str(local_path))
            except Exception as e:
                raise StudioCliError(
                    f"Could not download files/folders from the given Studio {studio}. "
                    "Please contact Lightning AI directly to resolve this issue."
                ) from e
