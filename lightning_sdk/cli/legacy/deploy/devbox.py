import concurrent.futures
import os
import re
import webbrowser
from pathlib import Path
from threading import Thread
from typing import Dict, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm
from rich.syntax import Syntax

from lightning_sdk import Machine
from lightning_sdk.cli.legacy.deploy._auth import (
    _AuthMode,
    _Onboarding,
    authenticate,
    poll_verified_status,
    select_teamspace,
)
from lightning_sdk.cli.legacy.upload import (
    _dump_current_upload_state,
    _resolve_previous_upload_state,
    _single_file_upload,
)
from lightning_sdk.lightning_cloud.openapi import V1CloudSpaceSourceType
from lightning_sdk.studio import Studio
from lightning_sdk.utils.resolve import _get_studio_url


# TODO: Move the rest of the devbox logic here
class _LitServeDevbox:
    """Build LitServe API in a Studio."""

    def resolve_previous_upload(self, studio: Studio, folder: str) -> Dict[str, str]:
        remote_path = "."
        pairs = {}
        for root, _, files in os.walk(folder):
            rel_root = os.path.relpath(root, folder)
            for f in files:
                pairs[os.path.join(root, f)] = os.path.join(remote_path, rel_root, f)
        return _resolve_previous_upload_state(studio, remote_path, pairs)

    def upload_folder(self, studio: Studio, folder: str, upload_state: Dict[str, str]) -> None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for k, v in upload_state.items():
                futures.append(
                    executor.submit(_single_file_upload, studio=studio, local_path=k, remote_path=v, progress_bar=False)
                )
            total_files = len(upload_state)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=Console(),
                transient=True,
            ) as progress:
                upload_task = progress.add_task(f"[cyan]Uploading {total_files} files to Studio...", total=total_files)
                for f in concurrent.futures.as_completed(futures):
                    upload_state.pop(f.result())
                    _dump_current_upload_state(studio, ".", upload_state)
                    progress.update(upload_task, advance=1)

    def _detect_port(self, script_path: Path) -> int:
        with open(script_path) as f:
            content = f.read()

        # Try to match server.run first and then any variable name and then default port=8000
        match = re.search(r"server\.run\s*\([^)]*port\s*=\s*(\d+)", content) or re.search(
            r"\w+\.run\s*\([^)]*port\s*=\s*(\d+)", content
        )
        return int(match.group(1)) if match else 8000


def _handle_devbox(
    name: str,
    script_path: Path,
    console: Console,
    non_interactive: bool = False,
    machine: Machine = Machine.CPU,
    interruptible: bool = False,
    teamspace: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None,
) -> None:
    if script_path.suffix != ".py":
        console.print("❌ Error: Only Python files (.py) are supported for development servers", style="red")
        return

    from_onboarding = False
    authenticate(_AuthMode.DEVBOX, shall_confirm=not non_interactive)
    user_status = poll_verified_status()
    if not user_status["verified"]:
        console.print("❌ Verify phone number to continue. Visit lightning.ai.", style="red")
        return
    if not user_status["onboarded"]:
        console.print("onboarding user")
        onboarding = _Onboarding(console)
        resolved_teamspace = onboarding.select_teamspace(teamspace, org, user)
        from_onboarding = True
    else:
        resolved_teamspace = select_teamspace(teamspace, org, user)
    studio = Studio(name=name, teamspace=resolved_teamspace, source=V1CloudSpaceSourceType.LITSERVE)
    studio.install_plugin("custom-port")
    lit_devbox = _LitServeDevbox()

    studio_url = _get_studio_url(studio, turn_on=True)
    pathlib_path = Path(script_path).resolve()
    browser_opened = False
    studio_path = f"{studio.owner.name}/{studio.teamspace.name}/{studio.name}"

    console.print("\n=== Lightning Studio Setup ===")
    console.print(f"🔧 [bold]Setting up Studio:[/bold] {studio_path}")
    console.print(f"📁 [bold]Local project:[/bold] {pathlib_path.parent}")

    upload_state = lit_devbox.resolve_previous_upload(studio, str(pathlib_path.parent))
    if non_interactive:
        console.print(f"🌐 [bold]Opening Studio:[/bold] [link={studio_url}]{studio_url}[/link]")
        browser_opened = webbrowser.open(studio_url)
    elif not from_onboarding:
        if Confirm.ask("Would you like to open your Studio in the browser?", default=True):
            console.print(f"🌐 [bold]Opening Studio:[/bold] [link={studio_url}]{studio_url}[/link]")
            browser_opened = webbrowser.open(studio_url)

    if not browser_opened:
        console.print(f"🔗 [bold]Access Studio:[/bold] [link={studio_url}]{studio_url}[/link]")

    # Start the Studio in the background and return immediately using threading
    console.print("\n⚡ Initializing Studio in the background...")
    studio_thread = Thread(target=studio.start, args=(machine, interruptible))
    studio_thread.start()

    console.print("📤 Syncing project files to Studio...")
    lit_devbox.upload_folder(studio, pathlib_path.parent, upload_state)

    # Wait for the Studio to start
    console.print("⚡ Waiting for Studio to start...")
    studio_thread.join()

    try:
        console.print("🚀 Starting server...")
        studio.run_and_detach(f"python {script_path}", timeout=10)
    except Exception as e:
        console.print("❌ Error while starting server", style="red")
        syntax = Syntax(f"{e}", "bash", theme="monokai")
        console.print(syntax)
        console.print(f"\n🔄 [bold]To fix:[/bold] Edit your code in Studio and run with: [u]python {script_path}[/u]")
        return

    port = lit_devbox._detect_port(pathlib_path)
    console.print("🔌 Configuring server port...")
    port_url = studio.run_plugin("custom-port", port=port)

    # Add completion message with next steps
    console.print("\n✅ Studio ready!")
    console.print("\n📋 [bold]Next steps:[/bold]")
    console.print("  [bold]1.[/bold] Server code will be available in the Studio")
    console.print("  [bold]2.[/bold] The Studio is now running with the specified configuration")
    console.print("  [bold]3.[/bold] Modify and run your server directly in the Studio")
    console.print(f"  [bold]4.[/bold] Your server will be accessible on [link={port_url}]{port_url}[/link]")
