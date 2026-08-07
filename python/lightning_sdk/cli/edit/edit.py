"""Edit a Drive file in place with a local editor."""

import contextlib
import hashlib
import io
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Iterator, Optional
from urllib.parse import quote

import rich_click as click
from rich.console import Console

from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.cli.cp import route_cp_operation
from lightning_sdk.utils.filesystem import parse_lit_url


@contextlib.contextmanager
def _quiet_transfer() -> Iterator[None]:
    """Silence the underlying copy's chatty output during an edit.

    The shared download/upload code prints its own progress bars and a ``See your file at
    <path>`` line pointing at the throwaway temp copy, which is confusing here. Captured
    output is re-emitted only if the transfer fails, so diagnostics are never lost.
    """
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            yield
    except BaseException:
        sys.stderr.write(buffer.getvalue())
        raise


def _content_digest(path: str) -> Optional[str]:
    """Return a sha256 digest of the file's contents, or ``None`` if it does not exist."""
    if not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_editor(editor: Optional[str]) -> str:
    """Resolve which editor command to launch: explicit ``--editor`` > ``$EDITOR`` > ``vim``."""
    return editor or os.environ.get("EDITOR") or "vim"


def _drive_url(remote_url: str) -> Optional[str]:
    """Build a browser link to the file in the teamspace Drive, or ``None`` if it can't be derived."""
    parsed = parse_lit_url(remote_url)
    owner, teamspace, destination = parsed["owner"], parsed["teamspace"], parsed["destination"]
    if not (owner and teamspace and destination):
        return None
    path = quote(destination, safe="")
    return f"{_get_cloud_url()}/{owner}/{teamspace}/drive?path={path}"


def route_edit_operation(remote_url: str, editor: Optional[str] = None) -> None:
    """Download a Drive file, open it in an editor, and re-upload it if it changed.

    Args:
        remote_url: The ``lit://`` URL of the file to edit.
        editor: The editor command to launch. Defaults to ``$EDITOR`` or ``vim``.

    Raises:
        ValueError: If ``remote_url`` is not a ``lit://`` URL.
    """
    console = Console()

    if not remote_url.startswith("lit://"):
        raise ValueError("The path to edit must be a remote lit:// URL.")

    if remote_url.endswith("/"):
        raise ValueError("The lit:// URL must point to a file, not a directory.")

    filename = os.path.basename(remote_url)
    if not filename:
        raise ValueError("The lit:// URL must point to a file, not a directory.")

    tmp_dir = tempfile.mkdtemp(prefix="lightning-edit-")
    local_path = os.path.join(tmp_dir, filename)

    try:
        console.print(f"Downloading [cyan]{remote_url}[/cyan] ...")
        with _quiet_transfer():
            route_cp_operation(source=remote_url, destination=local_path, recursive=False, progress_bar=False)

        before = _content_digest(local_path)

        editor_cmd = _resolve_editor(editor)
        console.print(f"Opening in [cyan]{editor_cmd}[/cyan] (save and close to upload) ...")
        try:
            return_code = subprocess.call([*shlex.split(editor_cmd), local_path])
        except FileNotFoundError:
            raise ValueError(
                f"Could not launch editor '{editor_cmd}'. "
                "Set the --editor option or the $EDITOR environment variable to a valid command."
            ) from None

        if return_code != 0:
            console.print(f"[yellow]Editor exited with code {return_code}; not uploading.[/yellow]")
            return

        after = _content_digest(local_path)
        if after is None:
            console.print("[yellow]File was deleted in the editor; nothing to upload.[/yellow]")
            return
        if after == before:
            console.print("No changes detected; nothing to upload.")
            return

        console.print(f"Uploading changes to [cyan]{remote_url}[/cyan] ...")
        with _quiet_transfer():
            route_cp_operation(source=local_path, destination=remote_url, recursive=False, progress_bar=False)
        console.print("[green]Done.[/green]")
        drive_url = _drive_url(remote_url)
        if drive_url:
            console.print(f"View it in the Drive: [link={drive_url}]{drive_url}[/link]")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def register_commands(command: click.Command) -> None:
    """Register the edit command callback."""

    def new_callback(path: str, editor: Optional[str] = None) -> None:
        route_edit_operation(remote_url=path, editor=editor)

    command.callback = new_callback
