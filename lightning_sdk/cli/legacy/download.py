import json
import os
import re
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from lightning_sdk.api.license_api import LicenseApi
from lightning_sdk.api.lit_container_api import LitContainerApi
from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.legacy.studios_menu import _StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.models import download_model
from lightning_sdk.studio import Studio
from lightning_sdk.utils.resolve import _get_authed_user, skip_studio_init


def _expand_remote_path(path: str) -> str:
    """Expand and normalize remote CLI paths.

    - Strips leading `~/` or `~`
    - Expands `~` to the user's home but returns relative to it
    - Returns an empty string if path is empty or `~`
    """
    if not path:
        return ""

    local_home = os.path.expanduser("~")

    # Expand to absolute path and remove the local home prefix if present
    path = os.path.expanduser(path)
    if path.startswith(local_home):
        path = path[len(local_home) :]

    # Remove any leading "/" or "~" remnants
    return path.lstrip("/~")


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
        "The name of the studio to download from. "
        "Will show a menu with user's owned studios for selection if not specified. "
        "If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME> where the names are case-sensitive. "
        "The teamspace and studio names can be regular expressions to match, "
        "a menu filtered studios will be shown for final selection."
    ),
)
@click.option(
    "--teamspace",
    default=None,
    help="The teamspace the drive folder is part of. Should be of format <OWNER>/<TEAMSPACE_NAME>.",
)
@click.option(
    "--local-path",
    "--local_path",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="The path to the directory you want to download the folder to.",
)
def folder(
    path: str = "", studio: Optional[str] = None, teamspace: Optional[str] = None, local_path: str = "."
) -> None:
    """Download a folder from a Studio or a Teamspace drive folder.

    Example:
      lightning download folder PATH

    PATH: The relative path within the Studio or drive folder you want to download.
    Defaults to the entire Studio or drive folder.
    """
    local_path = Path(local_path)
    if not local_path.is_dir():
        raise NotADirectoryError(f"'{local_path}' is not a directory")

    if studio and teamspace:
        raise ValueError("Either --studio or --teamspace must be provided, not both")

    if studio:
        path = _expand_remote_path(path)
        resolved_downloader = _resolve_studio(studio)
    elif teamspace:
        menu = TeamspacesMenu()
        resolved_downloader = menu(teamspace)
    else:
        raise ValueError("Either --studio or --teamspace must be provided")

    if not path:
        local_path /= resolved_downloader.name
        path = ""

    try:
        if not path and teamspace:
            raise FileNotFoundError()
        resolved_downloader.download_folder(remote_path=path, target_path=str(local_path))
    except Exception as e:
        raise StudioCliError(
            f"Could not download the folder from the given Studio {studio} or Teamspace {teamspace}. "
            "Please contact Lightning AI directly to resolve this issue."
        ) from e


@download.command(name="file")
@click.argument("path")
@click.option(
    "--studio",
    default=None,
    help=(
        "The name of the studio to download from. "
        "Will show a menu with user's owned studios for selection if not specified. "
        "If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME> where the names are case-sensitive. "
        "The teamspace and studio names can be regular expressions to match, "
        "a menu filtered studios will be shown for final selection."
    ),
)
@click.option(
    "--teamspace",
    default=None,
    help="The teamspace the file is part of. Should be of format <OWNER>/<TEAMSPACE_NAME>.",
)
@click.option(
    "--local-path",
    "--local_path",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="The path to the directory you want to download the file to.",
)
def file(path: str = "", studio: Optional[str] = None, teamspace: Optional[str] = None, local_path: str = ".") -> None:
    """Download a file from a Studio or Teamspace drive file.

    Example:
      lightning download file PATH

    PATH: The relative path to the file within the Studio or Teamspace drive file you want to download.
    """
    local_path = Path(local_path)
    if not local_path.is_dir():
        raise NotADirectoryError(f"'{local_path}' is not a directory")

    if studio and teamspace:
        raise ValueError("Either --studio or --teamspace must be provided, not both")

    if studio:
        resolved_downloader = _resolve_studio(studio)
    elif teamspace:
        menu = TeamspacesMenu()
        resolved_downloader = menu(teamspace)
    else:
        raise ValueError("Either --studio or --teamspace must be provided")

    if not path:
        local_path /= resolved_downloader.name
        path = ""

    try:
        if not path:
            raise FileNotFoundError()
        resolved_downloader.download_file(remote_path=path, file_path=str(local_path / os.path.basename(path)))
    except Exception as e:
        raise StudioCliError(
            f"Could not download the file from the given Studio {studio} or Teamspace {teamspace}. "
            "Please contact Lightning AI directly to resolve this issue."
        ) from e


@download.command(name="container")
@click.argument("container")
@click.option("--teamspace", default=None, help="The name of the teamspace to download the container from")
@click.option("--tag", default="latest", show_default=True, help="The tag of the container to download.")
@click.option(
    "--cloud-account",
    "--cloud_account",  # The UI will present the above variant, using this as a secondary to be consistent w/ models
    default=None,
    help="The name of the cloud account to download the Container from.",
)
def download_container(
    container: str, teamspace: Optional[str] = None, tag: str = "latest", cloud_account: Optional[str] = None
) -> None:
    """Download a docker container from a teamspace.

    Example:
      lightning download container CONTAINER

    CONTAINER: The name of the container to download.
    """
    console = Console()
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace)
    with console.status("Downloading container..."):
        api = LitContainerApi()
        api.download_container(container, resolved_teamspace, tag, cloud_account)
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
            f"Could not find the given Studio {studio} to download files from. "
            "Please contact Lightning AI directly to resolve this issue."
        ) from e

    with skip_studio_init():
        return Studio(**selected_studio)


@download.command(name="licenses")
def download_licenses() -> None:
    """Download licenses for all user's products/packages.

    Example:
      lightning download licenses

    """
    user = _get_authed_user()
    api = LicenseApi()
    licenses = api.list_user_licenses(user.id)

    user_home = Path.home()
    lit_dir = user_home / ".lightning"
    lit_dir.mkdir(parents=True, exist_ok=True)
    licenses_file = lit_dir / "licenses.json"

    licenses_short = {ll.product_name: ll.license_key for ll in licenses if ll.is_valid}
    with licenses_file.open("w") as fp:
        json.dump(licenses_short, fp, indent=4)
    Console().print(f"Licenses downloaded to {licenses_file}", style="green")


@download.command(name="license")
@click.argument("name")
def download_license(name: str) -> None:
    """Download license for specific products/packages.

    Example:
      lightning download license NAME

    NAME: The name of the product/package to download the license for.
    """
    user = _get_authed_user()
    api = LicenseApi()
    licenses = api.list_user_licenses(user.id)
    licenses_short = {ll.product_name: ll.license_key for ll in licenses if ll.is_valid}

    if name not in licenses_short:
        Console().print(f"Missing valid license for {name}", style="red")
        return

    user_home = Path.home()
    lit_dir = user_home / ".lightning"
    lit_dir.mkdir(parents=True, exist_ok=True)
    licenses_file = lit_dir / "licenses.json"

    licenses_loaded = {}
    if licenses_file.exists():
        with licenses_file.open("r") as fp:
            licenses_loaded = json.load(fp)

    licenses_loaded[name] = licenses_short[name]

    with licenses_file.open("w") as fp:
        json.dump(licenses_loaded, fp, indent=4)
    Console().print(f"Updated license for {name} in {licenses_file}", style="green")
