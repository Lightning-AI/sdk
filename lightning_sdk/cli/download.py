import os
import re
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from lightning_sdk.api.lit_container_api import LitContainerApi
from lightning_sdk.cli.exceptions import StudioCliError
from lightning_sdk.cli.studios_menu import _StudiosMenu
from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu
from lightning_sdk.models import download_model
from lightning_sdk.studio import Studio
from lightning_sdk.utils.resolve import _get_authed_user, skip_studio_init


@click.group(name="download")
def download() -> None:
    """Download resources from Lightning AI."""


@download.command(name="model")
@click.argument("name")
@click.option(
    "--download-dir", "--download_dir", default=".", help="The directory where the Model should be downloaded."
)
def model(name: str, download_dir: str = ".") -> None:
    """Download a model from a teamspace.

    Example:
      lightning download model NAME

    NAME: The name of the model to download in the format of <ORGANIZATION-NAME>/<TEAMSPACE-NAME>/<MODEL-NAME>.
    """
    download_model(
        name=name,
        download_dir=download_dir,
        progress_bar=True,
    )


@download.command(name="folder")
@click.argument("path")
@click.option(
    "--studio",
    default=None,
    help=(
        "The name of the studio to upload to. "
        "Will show a menu with user's owned studios for selection if not specified. "
        "If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME> where the names are case-sensitive. "
        "The teamspace and studio names can be regular expressions to match, "
        "a menu filtered studios will be shown for final selection."
    ),
)
@click.option(
    "--local-path",
    "--local_path",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="The path to the directory you want to download the folder to.",
)
def folder(path: str = "", studio: Optional[str] = None, local_path: str = ".") -> None:
    """Download a folder from a Studio.

    Example:
      lightning download folder PATH

    PATH: The relative path within the Studio you want to download.
    Defaults to the entire studio.
    """
    local_path = Path(local_path)
    if not local_path.is_dir():
        raise NotADirectoryError(f"'{local_path}' is not a directory")

    resolved_studio = _resolve_studio(studio)

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


@download.command(name="file")
@click.argument("path")
@click.option(
    "--studio",
    default=None,
    help=(
        "The name of the studio to upload to. "
        "Will show a menu with user's owned studios for selection if not specified. "
        "If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME> where the names are case-sensitive. "
        "The teamspace and studio names can be regular expressions to match, "
        "a menu filtered studios will be shown for final selection."
    ),
)
@click.option(
    "--local-path",
    "--local_path",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="The path to the directory you want to download the file to.",
)
def file(path: str = "", studio: Optional[str] = None, local_path: str = ".") -> None:
    """Download a file from a Studio.

    Example:
      lightning download file PATH

    PATH: The relative path to the file within the Studio you want to download.
    """
    local_path = Path(local_path)
    if not local_path.is_dir():
        raise NotADirectoryError(f"'{local_path}' is not a directory")

    resolved_studio = _resolve_studio(studio)

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


@download.command(name="container")
@click.argument("container")
@click.option("--teamspace", default=None, help="The name of the teamspace to download the container from")
@click.option("--tag", default="latest", show_default=True, help="The tag of the container to download.")
def download_container(container: str, teamspace: Optional[str] = None, tag: str = "latest") -> None:
    """Download a docker container from a teamspace.

    Example:
      lightning download container CONTAINER

    CONTAINER: The name of the container to download.
    """
    console = Console()
    menu = _TeamspacesMenu()
    resolved_teamspace = menu._resolve_teamspace(teamspace)
    with console.status("Downloading container..."):
        api = LitContainerApi()
        api.download_container(container, resolved_teamspace, tag)
        console.print("Container downloaded successfully", style="green")


def _resolve_studio(studio: Optional[str]) -> Studio:
    user = _get_authed_user()
    # if no studio specify suggest/filter only user's studios
    menu = _StudiosMenu()
    possible_studios = menu._get_possible_studios(user, is_owner=studio is None)

    try:
        if studio:
            team_name, studio_name = studio.split("/")
            options = [st for st in possible_studios if st["teamspace"] == team_name and st["name"] == studio_name]
            if len(options) == 1:
                selected_studio = menu._get_studio_from_name(studio, possible_studios)
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
                selected_studio = menu._get_studio_from_interactive_menu(list(possible_studios))
        else:
            selected_studio = menu._get_studio_from_interactive_menu(possible_studios)

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
