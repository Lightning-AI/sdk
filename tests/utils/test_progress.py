import pytest

from lightning_sdk.utils.progress import get_switching_progress_message


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
