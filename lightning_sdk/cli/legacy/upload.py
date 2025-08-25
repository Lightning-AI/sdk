import concurrent.futures
import json
import os
import webbrowser
from pathlib import Path
from typing import Dict, Generator, List, Optional

import click
import rich
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from simple_term_menu import TerminalMenu
from tqdm import tqdm

from lightning_sdk.api.lit_container_api import DockerNotRunningError, LCRAuthFailedError, LitContainerApi
from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.legacy.studios_menu import _StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.constants import _LIGHTNING_DEBUG
from lightning_sdk.models import upload_model as _upload_model
from lightning_sdk.studio import Studio
from lightning_sdk.utils.resolve import _get_authed_user, skip_studio_init

_STUDIO_UPLOAD_STATUS_PATH = "~/.lightning/studios/uploads"


@click.group("upload")
def upload() -> None:
    """Upload assets to Lightning AI."""


@upload.command("model")
@click.argument("name")
@click.option(
    "--path",
    default=".",
    help="The path to the file or directory you want to upload. Defaults to the current directory.",
)
@click.option(
    "--cloud-account",
    "--cloud_account",
    default=None,
    help="The name of the cloud account to store the Model in.",
)
def model(name: str, path: str = ".", cloud_account: Optional[str] = None) -> None:
    """Upload a model a teamspace.

    Example:
        lightning upload model NAME

    NAME: the name of the model to upload (Should be of format <ORGANIZATION-NAME>/<TEAMSPACE-NAME>/<MODEL-NAME>).
    """
    _upload_model(name, path, cloud_account=cloud_account)


@upload.command("folder")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--studio",
    default=None,
    help=(
        "The name of the studio to upload to. "
        "Will show a menu for selection if not specified. "
        "If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME>"
    ),
)
@click.option(
    "--remote-path",
    "--remote_path",
    default=None,
    help=(
        "The path where the uploaded file should appear on your Studio. "
        "Has to be within your Studio's home directory and will be relative to that. "
        "If not specified, will use the name of the folder you want to upload and place it in your home directory."
    ),
)
def folder(path: str, studio: Optional[str], remote_path: Optional[str]) -> None:
    """Upload a folder to a Studio."""
    _folder(path=path, studio=studio, remote_path=remote_path)


@upload.command("file")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--studio",
    default=None,
    help=(
        "The name of the studio to upload to. "
        "Will show a menu for selection if not specified. "
        "If provided, should be in the form of <TEAMSPACE-NAME>/<STUDIO-NAME>"
    ),
)
@click.option(
    "--remote-path",
    "--remote_path",
    default=None,
    help=(
        "The path where the uploaded file should appear on your Studio. "
        "Has to be within your Studio's home directory and will be relative to that. "
        "If not specified, will use the name of the file you want to upload and place it in your home directory."
    ),
)
def file(path: str, studio: Optional[str] = None, remote_path: Optional[str] = None) -> None:
    """Upload a file to a Studio."""
    _file(path=path, studio=studio, remote_path=remote_path)


@upload.command("container")
@click.argument("container")
@click.option("--tag", default="latest", help="The tag of the container to upload.")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace the studio is part of. "
        "Should be of format <OWNER>/<TEAMSPACE_NAME>. "
        "If not specified, tries to infer from the environment (e.g. when run from within a Studio.)"
    ),
)
@click.option(
    "--cloud-account",
    "--cloud_account",  # The UI will present the above variant, using this as a secondary to be consistent w/ models
    default=None,
    help="The name of the cloud account to store the Container in.",
)
@click.option(
    "--platform",
    default="linux/amd64",
    help="This is the platform the container pulled and push to Lightning AI will run on.",
)
def upload_container(
    container: str,
    tag: str = "latest",
    teamspace: Optional[str] = None,
    cloud_account: Optional[str] = None,
    platform: Optional[str] = "linux/amd64",
) -> None:
    """Upload a container to Lightning AI's container registry."""
    menu = TeamspacesMenu()
    teamspace = menu(teamspace)
    console = Console()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        try:
            if platform != "linux/amd64":
                console.print(
                    "[yellow]Warning: The platform you selected (" + platform + ") may not deploy successfully[/yellow]"
                )
            api = LitContainerApi()
            push_task = progress.add_task("Pushing Docker image", total=None)
            console.print("Authenticating with Lightning Container Registry...")
            try:
                api.authenticate()
                console.print("Authenticated with Lightning Container Registry", style="green")
            except Exception:
                # let the push with retry take control of auth moving forward
                pass

            lines = api.upload_container(container, teamspace, tag, cloud_account, platform, return_final_dict=True)
            _print_docker_push(lines, console, progress, push_task)
        except DockerNotRunningError as e:
            e.print_help()
            return
        except LCRAuthFailedError:
            console.print("Re-authenticating with Lightning Container Registry...")
            if not api.authenticate(reauth=True):
                raise StudioCliError("Failed to authenticate with Lightning Container Registry") from None
            console.print("Authenticated with Lightning Container Registry", style="green")
            lines = api.upload_container(container, teamspace, tag, cloud_account, platform)
            _print_docker_push(lines, console, progress, push_task)
        except Exception as e:
            if _LIGHTNING_DEBUG:
                print(e)
                if e.__cause__:
                    print(e.__cause__)

            progress.update(push_task, description=f"[bold red]Error: {e!s}[/]")
            progress.stop()
            return
        progress.update(push_task, description="[green]Container pushed![/green]")


def _folder(path: str, studio: Optional[str] = None, remote_path: Optional[str] = None) -> None:
    """Upload a folder to a Studio."""
    console = Console()
    if remote_path is None:
        remote_path = os.path.basename(path)

    if not Path(path).exists():
        raise FileNotFoundError(f"The provided path does not exist: {path}.")
    if not Path(path).is_dir():
        raise StudioCliError(f"The provided path is not a folder: {path}. Use `lightning upload file` instead.")

    selected_studio = _resolve_studio(studio)

    console.print(f"Uploading to {selected_studio.teamspace.name}/{selected_studio.name}")

    _upload_folder(path, remote_path, selected_studio)

    studio_url = (
        _get_cloud_url().replace(":443", "")
        + "/"
        + selected_studio.owner.name
        + "/"
        + selected_studio.teamspace.name
        + "/studios/"
        + selected_studio.name
    )
    console.print(f"See your files at {studio_url}")


def _upload_folder(path: str, remote_path: str, studio: Studio) -> None:
    pairs = {}
    for root, _, files in os.walk(path):
        rel_root = os.path.relpath(root, path)
        for f in files:
            pairs[os.path.join(root, f)] = os.path.join(remote_path, rel_root, f)

    upload_state = _resolve_previous_upload_state(studio, remote_path, pairs)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = _start_parallel_upload(executor, studio, upload_state)

        update_fn = tqdm(total=len(upload_state)).update if _global_upload_progress(upload_state) else lambda x: None

        for f in concurrent.futures.as_completed(futures):
            upload_state.pop(f.result())
            _dump_current_upload_state(studio, remote_path, upload_state)
            update_fn(1)


def _file(path: str, studio: Optional[str] = None, remote_path: Optional[str] = None) -> None:
    """Upload a file to a Studio."""
    console = Console()
    if remote_path is None:
        remote_path = os.path.basename(path)

    if Path(path).is_dir():
        raise StudioCliError(f"The provided path is a folder: {path}. Use `lightning upload folder` instead.")
    if not Path(path).exists():
        raise FileNotFoundError(f"The provided path does not exist: {path}.")

    selected_studio = _resolve_studio(studio)

    console.print(f"Uploading to {selected_studio.teamspace.name}/{selected_studio.name}")

    _single_file_upload(selected_studio, path, remote_path, True)

    studio_url = (
        _get_cloud_url().replace(":443", "")
        + "/"
        + selected_studio.owner.name
        + "/"
        + selected_studio.teamspace.name
        + "/studios/"
        + selected_studio.name
    )
    console.print(f"See your file at {studio_url}")


def _resolve_studio(studio: Optional[str]) -> Studio:
    user = _get_authed_user()
    menu = _StudiosMenu()
    possible_studios = menu._get_possible_studios(user)

    try:
        if studio is None:
            selected_studio = menu._get_studio_from_interactive_menu(possible_studios)
        else:
            selected_studio = menu._get_studio_from_name(studio, possible_studios)

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


def _print_docker_push(lines: Generator, console: Console, progress: Progress, push_task: rich.progress.TaskID) -> None:
    for line in lines:
        if "status" in line:
            console.print(line["status"], style="bright_black")
            progress.update(push_task, description="Pushing Docker image")
        elif "aux" in line:
            console.print(line["aux"], style="bright_black")
        elif "error" in line:
            progress.stop()
            console.print(f"\n[red]{line}[/red]")
            return
        elif "finish" in line:
            if "url" in line:
                webbrowser.open(line["url"])
            console.print(f"Container available at [i]{line['url']}[/i]")
            return
        else:
            console.print(line, style="bright_black")


def _start_parallel_upload(
    executor: concurrent.futures.ThreadPoolExecutor, studio: Studio, upload_state: Dict[str, str]
) -> List[concurrent.futures.Future]:
    # only add progress bar on individual uploads with less than 10 files
    progress_bar = not _global_upload_progress(upload_state)

    futures = []
    for k, v in upload_state.items():
        futures.append(
            executor.submit(_single_file_upload, studio=studio, local_path=k, remote_path=v, progress_bar=progress_bar)
        )

    return futures


def _single_file_upload(studio: Studio, local_path: str, remote_path: str, progress_bar: bool) -> str:
    studio.upload_file(local_path, remote_path, progress_bar)
    return local_path


def _dump_current_upload_state(studio: Studio, remote_path: str, state_dict: Dict[str, str]) -> None:
    """Dumps the current upload state so that we can safely resume later."""
    curr_path = os.path.abspath(
        os.path.expandvars(
            os.path.expanduser(os.path.join(_STUDIO_UPLOAD_STATUS_PATH, studio._studio.id, remote_path + ".json"))
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


def _resolve_previous_upload_state(studio: Studio, remote_path: str, state_dict: Dict[str, str]) -> Dict[str, str]:
    """Resolves potential previous uploads to continue if possible."""
    curr_path = os.path.abspath(
        os.path.expandvars(
            os.path.expanduser(os.path.join(_STUDIO_UPLOAD_STATUS_PATH, studio._studio.id, remote_path + ".json"))
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


def _global_upload_progress(upload_state: Dict[str, str]) -> bool:
    return len(upload_state) > 10
