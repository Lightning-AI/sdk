"""rm CLI command."""

import rich_click as click

from lightning_sdk.cli.cp.completion import complete_cp_path
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.filesystem import Filesystem


@click.command("rm", cls=LightningCommand)
@click.argument("path", nargs=1, shell_complete=complete_cp_path)
@click.option("-r", "--recursive", is_flag=True, help="Remove directories recursively")
@click.option("-f", "--force", is_flag=True, help="Ignore nonexistent files, never prompt")
def rm(path: str, recursive: bool = False, force: bool = False) -> None:
    """Remove a file or directory from a teamspace drive.

    PATH: Drive path to remove, in the format lit://<owner>/<teamspace>/<path>.

    Examples:
        lightning rm lit://<owner>/<my-teamspace>/uploads/file.txt
        lightning rm -r lit://<owner>/<my-teamspace>/artifacts/reports/

    """
    return rm_impl(path=path, recursive=recursive, force=force)


def rm_impl(path: str, recursive: bool = False, force: bool = False) -> None:
    if not path.startswith("lit://"):
        raise ValueError("Path must be a drive path starting with 'lit://'.")

    try:
        Filesystem().rm(path, recursive=recursive)
    except FileNotFoundError:
        if force:
            # silently ignore nonexistent files with -f flag
            return
        raise
    except ValueError as e:
        if "is a directory" in str(e):
            raise ValueError(f"{path!r} is a directory. Use the -r flag to remove directories recursively.") from None
        raise

    click.echo(f"Removed: {path}")
