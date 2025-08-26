"""Studio startup/switch progress bar utilities."""

import time
import types
from enum import Enum
from typing import Any, Callable, List, Optional, Type, Union

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn

from lightning_sdk.lightning_cloud.openapi.models.v1_cluster_accelerator import V1ClusterAccelerator
from lightning_sdk.lightning_cloud.openapi.models.v1_get_cloud_space_instance_status_response import (
    V1GetCloudSpaceInstanceStatusResponse,
)


class StartupPhase(Enum):
    """Studio startup phase messages."""

    ALLOCATING_MACHINE = "Allocating machine from cloud provider..."
    STUDIO_STARTING = "Studio is starting up..."
    SETTING_UP_ENVIRONMENT = "Setting up Studio environment..."
    RESTORING_STATE = "Restoring Studio state..."
    FINALIZING_SETUP = "Finalizing Studio setup..."
    COMPLETED = "Studio started successfully"


def get_switching_progress_message(percentage: int, is_base_studio: bool, is_new_cloud_space: bool) -> str:
    """Get progress message for switching studios."""
    percentage = max(0, min(100, round(percentage)))

    if percentage > 98:
        message = "Done"
    elif percentage > 80:
        if is_new_cloud_space:
            message = "Setting up Base Studio..." if is_base_studio else "Preparing Studio..."
        else:
            message = "Restoring Studio..."
    elif percentage > 60:
        message = "Setting up machine from cloud provider"
    else:
        message = "Allocating machine from cloud provider"

    return f"({percentage}%) {message}"


def estimated_studio_ready_in_seconds(
    cloud_space: Any, cloud_space_instance_status: Any, accelerators: Optional[List[V1ClusterAccelerator]] = None
) -> int:
    """Calculate estimated seconds until studio is ready."""
    # Default estimate
    return 120


def progress_bar_growth(default_timeout: int, counter: float) -> int:
    """Calculate progress bar growth based on timeout and counter."""
    if default_timeout <= 0:
        return 100

    value = ((default_timeout - counter) / default_timeout) * 100
    if value > 100:
        value = 100
    if value < 0:
        value = 0
    return int(value)


class StudioProgressTracker:
    """Tracks and displays progress for studio startup/switching operations."""

    def __init__(self, operation_type: str = "start", show_progress: bool = True, check_interval: float = 1.0) -> None:
        """Initialize progress tracker.

        Args:
            operation_type: Type of operation ('start' or 'switch')
            show_progress: Whether to display progress bar
            check_interval: Seconds between status checks
        """
        self.operation_type = operation_type
        self.show_progress = show_progress
        self.check_interval = check_interval
        self.progress: Optional[Progress] = None
        self.task_id: Optional[TaskID] = None
        self.console = Console()
        self._last_message = ""

    def __enter__(self) -> "StudioProgressTracker":
        """Enter context manager."""
        if self.show_progress:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console,
                transient=False,
            )
            self.progress.start()
            self.task_id = self.progress.add_task(f"{self.operation_type.capitalize()}ing Studio...", total=100)
        return self

    def __exit__(
        self,
        exc_type: Union[Type[BaseException], None],
        exc_val: Union[BaseException, None],
        exc_tb: Union[types.TracebackType, None],
    ) -> None:
        """Exit context manager."""
        if self.progress:
            self.progress.stop()

    def update_progress(
        self, percentage: int, message: str = "", is_base_studio: bool = False, is_new_cloud_space: bool = False
    ) -> None:
        """Update progress bar with current percentage and message."""
        if not self.progress or self.task_id is None:
            return

        if self.operation_type == "switch":
            display_message = get_switching_progress_message(percentage, is_base_studio, is_new_cloud_space)
        else:
            display_message = message or f"{self.operation_type.capitalize()}ing Studio..."

        # Update description if message changed
        if display_message != self._last_message:
            self.progress.update(self.task_id, description=display_message)
            self._last_message = display_message

        # Never show 100% until truly complete
        completed = min(percentage, 98) if percentage < 100 else 100
        self.progress.update(self.task_id, completed=completed)

        # Force console refresh to ensure progress is visible
        self.progress.refresh()

    def complete(self, success_message: str = "") -> None:
        """Mark operation as complete."""
        if self.progress and self.task_id is not None:
            self.progress.update(self.task_id, completed=100, description=success_message or "Done")

    def track_startup_phases(
        self,
        status_getter: Callable[[], V1GetCloudSpaceInstanceStatusResponse],
        accelerators: Optional[List[V1ClusterAccelerator]] = None,
        timeout: int = 600,
    ) -> None:
        """Track startup phases and update progress accordingly."""
        start_time = time.time()
        last_progress = 5
        phase_start_times = {}
        last_message_time = 0
        message_stability_delay = 3.0  # Seconds to wait before changing message

        # Show initial progress immediately
        self.update_progress(5, StartupPhase.ALLOCATING_MACHINE.value)

        while True:
            try:
                status = status_getter()
                elapsed = time.time() - start_time

                # Default fallback progress based on time
                time_based_progress = min(95, int((elapsed / timeout) * 100))
                current_progress = max(last_progress, time_based_progress)
                current_message = StartupPhase.ALLOCATING_MACHINE.value

                # Check if we have detailed status information
                if hasattr(status, "in_use") and status.in_use:
                    in_use = status.in_use

                    # Check startup status for detailed phases
                    if hasattr(in_use, "startup_status") and in_use.startup_status:
                        startup_status = in_use.startup_status

                        # Check completion first
                        if (
                            hasattr(startup_status, "top_up_restore_finished")
                            and startup_status.top_up_restore_finished
                        ):
                            self.complete(StartupPhase.COMPLETED.value)
                            break

                        # Check other phases in descending priority
                        if (
                            hasattr(startup_status, "initial_restore_finished")
                            and startup_status.initial_restore_finished
                        ):
                            current_progress = max(current_progress, 85)
                            current_message = StartupPhase.FINALIZING_SETUP.value
                        elif hasattr(startup_status, "container_ready") and startup_status.container_ready:
                            current_progress = max(current_progress, 70)
                            current_message = StartupPhase.RESTORING_STATE.value
                        elif hasattr(startup_status, "machine_ready") and startup_status.machine_ready:
                            current_progress = max(current_progress, 60)
                            current_message = StartupPhase.SETTING_UP_ENVIRONMENT.value

                    # Check general phase information
                    if hasattr(in_use, "phase") and in_use.phase:
                        phase = in_use.phase

                        if phase == "CLOUD_SPACE_INSTANCE_STATE_RUNNING":
                            current_progress = max(current_progress, 80)
                            current_message = StartupPhase.STUDIO_STARTING.value
                        elif phase == "CLOUD_SPACE_INSTANCE_STATE_PENDING":
                            # Track time in pending phase for smoother progress
                            if "pending" not in phase_start_times:
                                phase_start_times["pending"] = time.time()

                            pending_elapsed = time.time() - phase_start_times["pending"]
                            # Progress more smoothly through pending phase (10-60%)
                            pending_progress = 10 + min(50, int((pending_elapsed / 60) * 50))
                            current_progress = max(current_progress, pending_progress)
                            current_message = StartupPhase.ALLOCATING_MACHINE.value

                # Check for requested machine status (pre-allocation)
                elif hasattr(status, "requested") and status.requested:
                    if "allocation" not in phase_start_times:
                        phase_start_times["allocation"] = time.time()

                    allocation_elapsed = time.time() - phase_start_times["allocation"]
                    # Progress through allocation phase (5-30%)
                    allocation_progress = 5 + min(25, int((allocation_elapsed / 30) * 25))
                    current_progress = max(current_progress, allocation_progress)
                    current_message = StartupPhase.ALLOCATING_MACHINE.value

                # Ensure progress never decreases and moves smoothly
                if current_progress > last_progress:
                    # Smooth progress increases - don't jump too much at once
                    max_increment = 3 if current_progress - last_progress > 10 else current_progress - last_progress
                    current_progress = last_progress + max_increment

                current_progress = min(98, current_progress)  # Never show 100% until truly complete

                # Only update message if enough time has passed since last message change
                # or if this is the first message
                current_time = time.time()
                should_update_message = current_message != self._last_message and (
                    current_time - last_message_time >= message_stability_delay or last_message_time == 0
                )

                if should_update_message:
                    self.update_progress(current_progress, current_message)
                    last_message_time = current_time
                else:
                    # Update progress but keep existing message
                    if self.progress and self.task_id is not None:
                        self.progress.update(self.task_id, completed=current_progress)
                        self.progress.refresh()

                last_progress = current_progress

                # Break if we timeout
                if elapsed > timeout:
                    self.complete("Studio start may still be in progress...")
                    break

            except Exception:
                # Continue on API errors but still update progress
                elapsed = time.time() - start_time
                fallback_progress = min(95, max(last_progress, int((elapsed / timeout) * 100)))

                # Only update message if enough time has passed
                current_time = time.time()
                should_update_message = StartupPhase.ALLOCATING_MACHINE.value != self._last_message and (
                    current_time - last_message_time >= message_stability_delay or last_message_time == 0
                )

                if should_update_message:
                    self.update_progress(fallback_progress, StartupPhase.ALLOCATING_MACHINE.value)
                    last_message_time = current_time
                else:
                    # Update progress but keep existing message
                    if self.progress and self.task_id is not None:
                        self.progress.update(self.task_id, completed=fallback_progress)
                        self.progress.refresh()

                last_progress = fallback_progress

                if elapsed > timeout:
                    self.complete("Studio start may still be in progress...")
                    break

            time.sleep(self.check_interval)
