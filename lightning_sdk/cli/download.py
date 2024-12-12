import os
import re
from pathlib import Path
from typing import Optional

from lightning_sdk.cli.exceptions import StudioCliError
from lightning_sdk.cli.studios_menu import _StudiosMenu
from lightning_sdk.models import download_model
from lightning_sdk.studio import Studio
from lightning_sdk.utils.resolve import _get_authed_user, skip_studio_init


class _Downloads(_StudiosMenu):
    """Download files and folders from Lightning AI."""

    def model(self, name: str, download_dir: str = ".") -> None:
        """Download a Model.

        Args:
          name: The name of the Model you want to download.
            This should have the format <ORGANIZATION-NAME>/<TEAMSPACE-NAME>/<MODEL-NAME>.
          download_dir: The directory where the Model should be downloaded.
        """
        download_model(
            name=name,
            download_dir=download_dir,
            progress_bar=True,
        )

    def _resolve_studio(self, studio: Optional[str]) -> Studio:
        user = _get_authed_user()
        # if no studio specify suggest/filter only user's studios
        possible_studios = self._get_possible_studios(user, is_owner=studio is None)

        try:
            if studio:
                team_name, studio_name = studio.split("/")
                options = [st for st in possible_studios if st["teamspace"] == team_name and st["name"] == studio_name]
                if len(options) == 1:
                    selected_studio = self._get_studio_from_name(studio, possible_studios)
                # user can also use the partial studio name as secondary interactive selection
                else:
                    # filter matching simple reg expressions or start with the team and studio name
                    possible_studios = filter(
                        lambda st: (re.match(team_name, st["teamspace"]) or team_name in st["teamspace"])
                        and (re.match(studio_name, st["name"]) or studio_name in st["name"]),
                        possible_studios,
                    )
                    if not possible_studios:
                        raise ValueError(
                            f"Could not find Studio like '{studio}', please consider update your filtering pattern."
                        )
                    selected_studio = self._get_studio_from_interactive_menu(list(possible_studios))
            else:
                selected_studio = self._get_studio_from_interactive_menu(possible_studios)

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

    def folder(self, path: str = "", studio: Optional[str] = None, local_path: str = ".") -> None:
        """Download a folder from a Studio.

        Args:
          path: The relative path within the Studio you want to download.
            If you leave it empty it will download whole studio and locally creates a new folder
            with the same name as the selected studio.
          studio: The name of the studio to upload to. Will show a menu with user's owned studios for selection
            if not specified. If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME> where the names
            are case-sensitive. The teamspace and studio names can be regular expressions to match, then a menu
            with filtered studios will be shown for final selection.
          local_path: The path to the directory you want to download the folder to.
        """
        local_path = Path(local_path)
        if not local_path.is_dir():
            raise NotADirectoryError(f"'{local_path}' is not a directory")

        resolved_studio = self._resolve_studio(studio)

        if not path:
            local_path /= resolved_studio.name
            path = ""

        try:
            if not path:
                raise FileNotFoundError()
            resolved_studio.download_folder(remote_path=path, target_path=str(local_path))
        except Exception as e:
            raise StudioCliError(
                f"Could not download the folder from the given Studio {studio}. "
                "Please contact Lightning AI directly to resolve this issue."
            ) from e

    def file(self, path: str = "", studio: Optional[str] = None, local_path: str = ".") -> None:
        """Download a file from a Studio.

        Args:
          path: The relative path within the Studio you want to download.
          studio: The name of the studio to upload to. Will show a menu with user's owned studios for selection
            if not specified. If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME> where the names
            are case-sensitive. The teamspace and studio names can be regular expressions to match, then a menu
            with filtered studios will be shown for final selection.
          local_path: The path to the directory you want to download the file to.
        """
        local_path = Path(local_path)
        if not local_path.is_dir():
            raise NotADirectoryError(f"'{local_path}' is not a directory")

        resolved_studio = self._resolve_studio(studio)

        if not path:
            local_path /= resolved_studio.name
            path = ""

        try:
            if not path:
                raise FileNotFoundError()
            resolved_studio.download_file(remote_path=path, file_path=str(local_path / os.path.basename(path)))
        except Exception as e:
            raise StudioCliError(
                f"Could not download the file from the given Studio {studio}. "
                "Please contact Lightning AI directly to resolve this issue."
            ) from e
