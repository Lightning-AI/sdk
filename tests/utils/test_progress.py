import pytest

from lightning_sdk.utils.progress import get_switching_progress_message


class TestGetSwitchingProgressMessage:
    """Test the get_switching_progress_message function."""

    def test_done_message(self):
        """Test message when progress is above 98%."""
        # Test above 98%
        result = get_switching_progress_message(99, False, False)
        assert result == "(99%) Done"

        result = get_switching_progress_message(100, False, False)
        assert result == "(100%) Done"

        # Parameters shouldn't matter for done state
        result = get_switching_progress_message(99, True, True)
        assert result == "(99%) Done"

    def test_restoring_phase(self):
        """Test message when progress is 80-98% for existing studios."""
        result = get_switching_progress_message(85, False, False)
        assert result == "(85%) Restoring Studio..."

        result = get_switching_progress_message(98, False, False)
        assert result == "(98%) Restoring Studio..."

    def test_new_base_studio_phase(self):
        """Test message when progress is 80-98% for new base studios."""
        result = get_switching_progress_message(85, True, True)
        assert result == "(85%) Setting up Base Studio..."

        result = get_switching_progress_message(90, True, True)
        assert result == "(90%) Setting up Base Studio..."

    def test_new_regular_studio_phase(self):
        """Test message when progress is 80-98% for new regular studios."""
        result = get_switching_progress_message(85, False, True)
        assert result == "(85%) Preparing Studio..."

        result = get_switching_progress_message(90, False, True)
        assert result == "(90%) Preparing Studio..."

    def test_setting_up_machine_phase(self):
        """Test message when progress is 60-80%."""
        result = get_switching_progress_message(65, False, False)
        assert result == "(65%) Setting up machine from the cloud provider"

        result = get_switching_progress_message(79, True, True)
        assert result == "(79%) Setting up machine from the cloud provider"

    def test_allocating_machine_phase(self):
        """Test message when progress is 0-60%."""
        result = get_switching_progress_message(0, False, False)
        assert result == "(0%) Allocating machine from the cloud provider"

        result = get_switching_progress_message(30, False, False)
        assert result == "(30%) Allocating machine from the cloud provider"

        result = get_switching_progress_message(59, True, True)
        assert result == "(59%) Allocating machine from the cloud provider"

    def test_percentage_bounds(self):
        """Test that percentage is properly bounded."""
        # Test negative percentage
        result = get_switching_progress_message(-10, False, False)
        assert result == "(0%) Allocating machine from the cloud provider"

        # Test percentage over 100
        result = get_switching_progress_message(150, False, False)
        assert result == "(100%) Done"

    def test_percentage_rounding(self):
        """Test that percentage is properly rounded."""
        result = get_switching_progress_message(85.7, False, False)
        assert result == "(86%) Restoring Studio..."

        result = get_switching_progress_message(85.3, False, False)
        assert result == "(85%) Restoring Studio..."

    def test_boundary_conditions(self):
        """Test exact boundary values."""
        # Test exactly at 60%
        result = get_switching_progress_message(60, False, False)
        assert result == "(60%) Allocating machine from the cloud provider"

        # Test exactly at 61%
        result = get_switching_progress_message(61, False, False)
        assert result == "(61%) Setting up machine from the cloud provider"

        # Test exactly at 80%
        result = get_switching_progress_message(80, False, False)
        assert result == "(80%) Setting up machine from the cloud provider"

        # Test exactly at 81%
        result = get_switching_progress_message(81, False, False)
        assert result == "(81%) Restoring Studio..."

    @pytest.mark.parametrize(
        ("percentage", "expected_phase"),
        [
            (0, "Allocating"),
            (30, "Allocating"),
            (59, "Allocating"),
            (60, "Allocating"),
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
        result = get_switching_progress_message(percentage, False, False)

        if expected_phase == "Allocating":
            assert "Allocating machine" in result
        elif expected_phase == "Setting up":
            assert "Setting up machine" in result
        elif expected_phase == "Restoring":
            assert "Restoring Studio" in result
        elif expected_phase == "Done":
            assert "Done" in result
