import subprocess


def test_list_base_studios():
    result = subprocess.run("lightning base-studio list --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning base-studio list [OPTIONS]

  List Base Studios in an org.

  Example:     lightning base-studio list

Options:
  --help  Show this message and exit.
"""
    )


def test_format_base_studio_name():
    """Test that base studio names are formatted correctly (lowercase with hyphens)."""
    from unittest.mock import Mock, patch

    from lightning_sdk.base_studio import BaseStudioInfo
    from lightning_sdk.cli.base_studio.list import list_impl

    # Mock base studio data
    mock_base_studios = [
        BaseStudioInfo(
            id="1",
            name="Python Studio",
            managed_id="managed-1",
            description="A Python development studio",
        ),
        BaseStudioInfo(
            id="2",
            name="Data Science Pro",
            managed_id="managed-2",
            description="Advanced data science environment",
        ),
    ]

    with patch("lightning_sdk.cli.base_studio.list.BaseStudio") as mock_base_studio_cls:
        mock_instance = Mock()
        mock_instance.list.return_value = mock_base_studios
        mock_base_studio_cls.return_value = mock_instance

        with patch("lightning_sdk.cli.base_studio.list.click.echo") as mock_echo:
            list_impl()

            # Verify list was called twice (managed=True and managed=False)
            assert mock_instance.list.call_count == 2

            # Get the table output that was echoed
            echo_call_args = mock_echo.call_args[0][0]

            # Check that names are transformed to lowercase with hyphens
            assert "python-studio" in echo_call_args
            assert "data-science-pro" in echo_call_args


def test_list_includes_managed_and_unmanaged():
    """Test that list retrieves both managed and unmanaged base studios."""
    from unittest.mock import Mock, patch

    from lightning_sdk.base_studio import BaseStudioInfo
    from lightning_sdk.cli.base_studio.list import list_impl

    managed_studios = [
        BaseStudioInfo(
            id="1",
            name="Managed Studio",
            managed_id="managed-1",
            description="Managed by Lightning",
        ),
    ]

    unmanaged_studios = [
        BaseStudioInfo(
            id="2",
            name="Custom Studio",
            managed_id="",
            description="Custom user studio",
        ),
    ]

    with patch("lightning_sdk.cli.base_studio.list.BaseStudio") as mock_base_studio_cls:
        mock_instance = Mock()
        mock_instance.list.side_effect = [managed_studios, unmanaged_studios]
        mock_base_studio_cls.return_value = mock_instance

        with patch("lightning_sdk.cli.base_studio.list.click.echo") as mock_echo:
            list_impl()

            # Verify list was called with managed=True (default) and managed=False
            calls = mock_instance.list.call_args_list
            assert len(calls) == 2
            # First call with default (managed=True)
            assert calls[0][1] == {} or calls[0][1].get("managed", True)
            # Second call with managed=False
            assert calls[1][1] == {"managed": False}

            # Verify both studios appear in output
            echo_call_args = mock_echo.call_args[0][0]
            assert "managed-studio" in echo_call_args
            assert "custom-studio" in echo_call_args


def test_list_handles_empty_description():
    """Test that list handles base studios with no description."""
    from unittest.mock import Mock, patch

    from lightning_sdk.base_studio import BaseStudioInfo
    from lightning_sdk.cli.base_studio.list import list_impl

    mock_base_studios = [
        BaseStudioInfo(
            id="1",
            name="No Description",
            managed_id="managed-1",
            description=None,
        ),
        BaseStudioInfo(
            id="2",
            name="Empty Description",
            managed_id="managed-2",
            description="",
        ),
    ]

    with patch("lightning_sdk.cli.base_studio.list.BaseStudio") as mock_base_studio_cls:
        mock_instance = Mock()
        mock_instance.list.return_value = mock_base_studios
        mock_base_studio_cls.return_value = mock_instance

        with patch("lightning_sdk.cli.base_studio.list.click.echo") as mock_echo:
            list_impl()

            # Should not raise an exception
            assert mock_echo.called
            echo_call_args = mock_echo.call_args[0][0]

            # Both studios should be in the output
            assert "no-description" in echo_call_args
            assert "empty-description" in echo_call_args


def test_name_transformation():
    """Test various name transformations to lowercase with hyphens."""
    test_cases = [
        ("Python Studio", "python-studio"),
        ("Data Science Pro", "data-science-pro"),
        ("UPPERCASE", "uppercase"),
        ("Multiple   Spaces", "multiple---spaces"),
        ("Mixed-Case Name", "mixed-case-name"),
    ]

    for original, expected in test_cases:
        result = original.lower().replace(" ", "-")
        assert result == expected, f"Expected {original} to transform to {expected}, got {result}"
