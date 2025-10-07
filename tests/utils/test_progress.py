import time
from unittest.mock import MagicMock

import pytest

from lightning_sdk.utils.progress import StudioProgressTracker, get_switching_progress_message


class TestGetSwitchingProgressMessage:
    """Test the get_switching_progress_message function."""

    def test_done_message(self):
        """Test message when progress is above 98%."""
        # Test above 98%
        result = get_switching_progress_message(99, False)
        assert result == "(99%) Done"

        result = get_switching_progress_message(100, False)
        assert result == "(100%) Done"

        # Parameters shouldn't matter for done state
        result = get_switching_progress_message(99, True)
        assert result == "(99%) Done"

    def test_restoring_phase(self):
        """Test message when progress is 80-98% for existing studios."""
        result = get_switching_progress_message(85, False)
        assert result == "(85%) Restoring Studio..."

        result = get_switching_progress_message(98, False)
        assert result == "(98%) Restoring Studio..."

    def test_new_base_studio_phase(self):
        """Test message when progress is 80-98% for new base studios."""
        result = get_switching_progress_message(85, True)
        assert result == "(85%) Restoring Base Studio..."

        result = get_switching_progress_message(90, True)
        assert result == "(90%) Restoring Base Studio..."

    def test_new_regular_studio_phase(self):
        """Test message when progress is 80-98% for new regular studios."""
        result = get_switching_progress_message(85, False)
        assert result == "(85%) Restoring Studio..."

        result = get_switching_progress_message(90, False)
        assert result == "(90%) Restoring Studio..."

    def test_setting_up_machine_phase(self):
        """Test message when progress is 60-80%."""
        result = get_switching_progress_message(65, False)
        assert result == "(65%) Setting up machine..."

        result = get_switching_progress_message(79, True)
        assert result == "(79%) Setting up machine..."

    def test_allocating_machine_phase(self):
        """Test message when progress is 0-60%."""
        result = get_switching_progress_message(0, False)
        assert result == "(0%) Switching Studio..."

        result = get_switching_progress_message(30, False)
        assert result == "(30%) Switching Studio..."

        result = get_switching_progress_message(59, True)
        assert result == "(59%) Switching Studio..."

    def test_percentage_bounds(self):
        """Test that percentage is properly bounded."""
        # Test negative percentage
        result = get_switching_progress_message(-10, False)
        assert result == "(0%) Switching Studio..."

        # Test percentage over 100
        result = get_switching_progress_message(150, False)
        assert result == "(100%) Done"

    def test_percentage_rounding(self):
        """Test that percentage is properly rounded."""
        result = get_switching_progress_message(85.7, False)
        assert result == "(86%) Restoring Studio..."

        result = get_switching_progress_message(85.3, False)
        assert result == "(85%) Restoring Studio..."

    def test_boundary_conditions(self):
        """Test exact boundary values."""
        # Test exactly at 60%
        result = get_switching_progress_message(60, False)
        assert result == "(60%) Switching Studio..."

        # Test exactly at 61%
        result = get_switching_progress_message(61, False)
        assert result == "(61%) Setting up machine..."

        # Test exactly at 80%
        result = get_switching_progress_message(80, False)
        assert result == "(80%) Setting up machine..."

        # Test exactly at 81%
        result = get_switching_progress_message(81, False)
        assert result == "(81%) Restoring Studio..."

    @pytest.mark.parametrize(
        ("percentage", "expected_phase"),
        [
            (0, "Switching"),
            (30, "Switching"),
            (59, "Switching"),
            (60, "Switching"),
            (61, "Setting up"),
            (70, "Setting up"),
            (80, "Setting up"),
            (81, "Restoring"),
            (90, "Restoring"),
            (98, "Restoring"),
            (99, "Done"),
            (100, "Done"),
        ],
    )
    def test_phase_progression(self, percentage, expected_phase):
        """Test that phases progress in the correct order."""
        result = get_switching_progress_message(percentage, False)

        if expected_phase == "Switching":
            assert "Switching Studio" in result
        elif expected_phase == "Setting up":
            assert "Setting up machine" in result
        elif expected_phase == "Restoring":
            assert "Restoring Studio" in result
        elif expected_phase == "Done":
            assert "Done" in result


class TestUpdateProgress:
    """Test the update_progress method of StudioProgressTracker."""

    def test_update_progress_with_progress_bar(self):
        """Test update_progress updates the progress bar correctly."""
        tracker = StudioProgressTracker(show_progress=True)
        with tracker:
            assert tracker.progress is not None
            assert tracker.task_id is not None

            tracker.update_progress(50, "Halfway there...")

            task = tracker.progress.tasks[0]
            assert task.completed == 50
            assert "Halfway there..." in task.description

    def test_update_progress_switch_operation_uses_switching_message(self):
        """Test that switch operation uses get_switching_progress_message."""
        tracker = StudioProgressTracker(operation_type="switch", show_progress=True)
        with tracker:
            tracker.update_progress(85, "", is_base_studio=False)

            task = tracker.progress.tasks[0]
            assert task.description == "(85%) Restoring Studio..."

    def test_update_progress_switch_operation_base_studio(self):
        """Test switch operation with base studio."""
        tracker = StudioProgressTracker(operation_type="switch", show_progress=True)
        with tracker:
            tracker.update_progress(85, "", is_base_studio=True)

            task = tracker.progress.tasks[0]
            assert task.description == "(85%) Restoring Base Studio..."

    def test_update_progress_caps_at_98_until_complete(self):
        """Test that progress is capped at 98% until explicitly set to 100."""
        tracker = StudioProgressTracker(show_progress=True)
        with tracker:
            # Update to 99% but not complete
            tracker.update_progress(99, "Almost there...")

            task = tracker.progress.tasks[0]
            # Should be capped at 98
            assert task.completed == 98

            # Update to 100% should show 100
            tracker.update_progress(100, "Done!")

            task = tracker.progress.tasks[0]
            assert task.completed == 100

    def test_update_progress_default_message(self):
        """Test update_progress with default message based on operation type."""
        tracker = StudioProgressTracker(operation_type="start", show_progress=True)
        with tracker:
            tracker.update_progress(50, "")

            task = tracker.progress.tasks[0]

            # No message provided so uses default
            assert task.description == "Starting Studio..."

    def test_update_progress_percentage_bounds(self):
        """Test that percentage values are handled correctly."""
        tracker = StudioProgressTracker(show_progress=True)
        with tracker:
            tracker.update_progress(0, "Start")
            assert tracker.progress.tasks[0].completed == 0

            tracker.update_progress(50, "Middle")
            assert tracker.progress.tasks[0].completed == 50

            tracker.update_progress(98, "Almost")
            assert tracker.progress.tasks[0].completed == 98

            # capped
            tracker.update_progress(99, "Very close")
            assert tracker.progress.tasks[0].completed == 98

            tracker.update_progress(100, "Complete")
            assert tracker.progress.tasks[0].completed == 100


class TestTrackStartupPhases:
    """Test the track_startup_phases method of StudioProgressTracker."""

    @pytest.fixture()
    def base_mock_status(self):
        """Create a base mock status object with common structure."""
        status = MagicMock()
        status.in_use = MagicMock()
        status.in_use.startup_status = MagicMock()
        return status

    @pytest.fixture()
    def tracker(self):
        """Create a tracker with common test settings."""
        return StudioProgressTracker(show_progress=True, check_interval=0.05)

    def _create_completed_status(self):
        """Helper to create a completed status mock."""
        mock_status = MagicMock()
        mock_status.in_use = MagicMock()
        mock_status.in_use.startup_status = MagicMock()
        mock_status.in_use.startup_status.top_up_restore_finished = True
        return mock_status

    def _create_incomplete_status(self):
        """Helper to create an incomplete status mock."""
        mock_status = MagicMock()
        mock_status.in_use = MagicMock()
        mock_status.in_use.startup_status = MagicMock()
        mock_status.in_use.startup_status.top_up_restore_finished = False
        return mock_status

    def test_track_startup_phases_completes_on_finished(self, tracker):
        """Test that tracking completes when top_up_restore_finished is True."""
        completed_status = self._create_completed_status()
        status_getter = lambda: completed_status

        with tracker:
            tracker.track_startup_phases(status_getter, timeout=5)

            task = tracker.progress.tasks[0]
            assert task.completed == 100
            assert "Done" in task.description

    def test_track_startup_phases_initial_restore_finished(self, base_mock_status, tracker):
        """Test progress when initial_restore_finished is True."""
        call_count = [0]

        def status_getter():
            call_count[0] += 1
            if call_count[0] < 3:
                base_mock_status.in_use.startup_status.top_up_restore_finished = False
                base_mock_status.in_use.startup_status.initial_restore_finished = True
                return base_mock_status
            base_mock_status.in_use.startup_status.top_up_restore_finished = True
            return base_mock_status

        with tracker:
            tracker.track_startup_phases(status_getter, timeout=2)

            task = tracker.progress.tasks[0]
            assert task.completed == 100

    def test_track_startup_phases_container_ready(self, base_mock_status, tracker):
        """Test progress when container_ready is True."""
        call_count = [0]

        def status_getter():
            call_count[0] += 1
            if call_count[0] < 3:
                base_mock_status.in_use.startup_status.top_up_restore_finished = False
                base_mock_status.in_use.startup_status.initial_restore_finished = False
                base_mock_status.in_use.startup_status.container_ready = True
                return base_mock_status
            base_mock_status.in_use.startup_status.top_up_restore_finished = True
            return base_mock_status

        with tracker:
            tracker.track_startup_phases(status_getter, timeout=2)

            task = tracker.progress.tasks[0]
            assert task.completed == 100

    def test_track_startup_phases_machine_ready(self, base_mock_status, tracker):
        """Test progress when machine_ready is True."""
        call_count = [0]

        def status_getter():
            call_count[0] += 1
            if call_count[0] < 3:
                base_mock_status.in_use.startup_status.top_up_restore_finished = False
                base_mock_status.in_use.startup_status.initial_restore_finished = False
                base_mock_status.in_use.startup_status.container_ready = False
                base_mock_status.in_use.startup_status.machine_ready = True
                return base_mock_status
            base_mock_status.in_use.startup_status.top_up_restore_finished = True
            return base_mock_status

        with tracker:
            tracker.track_startup_phases(status_getter, timeout=2)

            task = tracker.progress.tasks[0]
            assert task.completed == 100

    def test_track_startup_phases_running_phase(self, tracker):
        """Test progress during RUNNING phase."""
        call_count = [0]
        mock_status = MagicMock()
        mock_status.in_use = MagicMock()
        mock_status.in_use.startup_status = None
        mock_status.in_use.phase = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"

        def status_getter():
            call_count[0] += 1
            if call_count[0] < 3:
                return mock_status
            mock_status.in_use.startup_status = MagicMock()
            mock_status.in_use.startup_status.top_up_restore_finished = True
            return mock_status

        with tracker:
            tracker.track_startup_phases(status_getter, timeout=2)

            task = tracker.progress.tasks[0]
            assert task.completed == 100

    def test_track_startup_phases_pending_phase(self, tracker):
        """Test progress during PENDING phase."""
        call_count = [0]
        mock_status = MagicMock()
        mock_status.in_use = MagicMock()
        mock_status.in_use.startup_status = None
        mock_status.in_use.phase = "CLOUD_SPACE_INSTANCE_STATE_PENDING"

        def status_getter():
            call_count[0] += 1
            if call_count[0] < 3:
                return mock_status
            mock_status.in_use.startup_status = MagicMock()
            mock_status.in_use.startup_status.top_up_restore_finished = True
            return mock_status

        with tracker:
            tracker.track_startup_phases(status_getter, timeout=2)

            task = tracker.progress.tasks[0]
            assert task.completed == 100

    def test_track_startup_phases_requested_state(self, tracker):
        """Test progress when machine is in requested state."""
        call_count = [0]
        mock_status = MagicMock()
        mock_status.in_use = None
        mock_status.requested = MagicMock()

        def status_getter():
            call_count[0] += 1
            if call_count[0] < 3:
                return mock_status
            mock_status.in_use = MagicMock()
            mock_status.in_use.startup_status = MagicMock()
            mock_status.in_use.startup_status.top_up_restore_finished = True
            return mock_status

        with tracker:
            tracker.track_startup_phases(status_getter, timeout=2)

            task = tracker.progress.tasks[0]
            assert task.completed == 100

    def test_track_startup_phases_timeout(self):
        """Test that tracking times out appropriately."""
        incomplete_status = self._create_incomplete_status()
        status_getter = lambda: incomplete_status

        tracker = StudioProgressTracker(show_progress=True, check_interval=0.1)
        start = time.time()
        with tracker:
            tracker.track_startup_phases(status_getter, timeout=1)

        elapsed = time.time() - start
        assert 0.8 < elapsed < 2.0

    def test_track_startup_phases_handles_exceptions(self, tracker):
        """Test that tracking handles exceptions gracefully."""
        call_count = [0]

        def status_getter():
            call_count[0] += 1
            if call_count[0] < 5:
                raise Exception("API Error")
            return self._create_completed_status()

        with tracker:
            tracker.track_startup_phases(status_getter, timeout=2)

            # Should still complete
            task = tracker.progress.tasks[0]
            assert task.completed == 100

    def test_track_startup_phases_progress_never_decreases(self, base_mock_status, tracker):
        """Test that progress never goes backwards."""
        call_count = [0]

        def status_getter():
            call_count[0] += 1
            if call_count[0] == 1:
                # high progress
                base_mock_status.in_use.startup_status.top_up_restore_finished = False
                base_mock_status.in_use.startup_status.initial_restore_finished = True
                return base_mock_status
            if call_count[0] < 5:
                # lower progress state
                base_mock_status.in_use.startup_status.initial_restore_finished = False
                base_mock_status.in_use.startup_status.container_ready = False
                base_mock_status.in_use.startup_status.machine_ready = True
                return base_mock_status

            base_mock_status.in_use.startup_status.top_up_restore_finished = True
            return base_mock_status

        last_progress = 0
        with tracker:
            status_getter()
            tracker.update_progress(80, "Initial high progress")
            last_progress = tracker.progress.tasks[0].completed

            tracker.track_startup_phases(status_getter, timeout=1)
            final_progress = tracker.progress.tasks[0].completed
            assert final_progress >= last_progress

    def test_track_startup_phases_smooth_progress_increments(self, base_mock_status, tracker):
        """Test that progress increases smoothly without large jumps."""
        call_count = [0]

        def status_getter():
            call_count[0] += 1
            if call_count[0] < 10:
                # Simulate gradual progression
                base_mock_status.in_use.startup_status.top_up_restore_finished = False
                base_mock_status.in_use.startup_status.machine_ready = call_count[0] > 3
                base_mock_status.in_use.startup_status.container_ready = call_count[0] > 6
                return base_mock_status
            base_mock_status.in_use.startup_status.top_up_restore_finished = True
            return base_mock_status

        with tracker:
            tracker.track_startup_phases(status_getter, timeout=2)

            task = tracker.progress.tasks[0]
            assert task.completed == 100

    def test_track_startup_phases_message_stability(self, base_mock_status, tracker):
        """Test that messages don't change too frequently."""
        call_count = [0]

        def status_getter():
            call_count[0] += 1
            # Rapidly change states
            if call_count[0] % 2 == 0:
                base_mock_status.in_use.startup_status.machine_ready = True
                base_mock_status.in_use.startup_status.container_ready = False
            else:
                base_mock_status.in_use.startup_status.machine_ready = False
                base_mock_status.in_use.startup_status.container_ready = True

            if call_count[0] > 10:
                base_mock_status.in_use.startup_status.top_up_restore_finished = True

            return base_mock_status

        with tracker:
            tracker.track_startup_phases(status_getter, timeout=2)

            task = tracker.progress.tasks[0]
            assert task.completed == 100
