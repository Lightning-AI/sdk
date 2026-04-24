from tests.cli.help import assert_help_contains, command_text


def test_list_base_studios():
    result_text = command_text("lightning base-studio list --help")

    assert "Usage: lightning base-studio list [OPTIONS]" in result_text
    assert "List Base Studios in an org." in result_text
    assert "Example:     lightning base-studio list" in result_text
    assert "--include-disabled" in result_text
    assert "Show this message and exit." in result_text


def test_list_base_studios_plural_help():
    assert_help_contains(
        "lightning base-studios list --help", "Usage: lightning base-studios list", "List Base Studios in an org."
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
            creator="⚡ Lightning AI",
            enabled=True,
        ),
        BaseStudioInfo(
            id="2",
            name="Data Science Pro",
            managed_id="managed-2",
            description="Advanced data science environment",
            creator="⚡ Lightning AI",
            enabled=True,
        ),
    ]

    with patch("lightning_sdk.cli.base_studio.list.BaseStudio") as mock_base_studio_cls:
        mock_instance = Mock()
        mock_instance.list.return_value = mock_base_studios
        mock_base_studio_cls.return_value = mock_instance

        with patch("lightning_sdk.cli.base_studio.list.click.echo") as mock_echo:
            list_impl(include_disabled=False)

            # Verify list was called
            assert mock_instance.list.call_count == 1

            # Get the table output that was echoed
            echo_call_args = mock_echo.call_args[0][0]

            # Check that names are transformed to lowercase with hyphens
            assert "python-studio" in echo_call_args
            assert "data-science-pro" in echo_call_args


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
            creator="⚡ Lightning AI",
            enabled=True,
        ),
        BaseStudioInfo(
            id="2",
            name="Empty Description",
            managed_id="managed-2",
            description="",
            creator="⚡ Lightning AI",
            enabled=True,
        ),
    ]

    with patch("lightning_sdk.cli.base_studio.list.BaseStudio") as mock_base_studio_cls:
        mock_instance = Mock()
        mock_instance.list.return_value = mock_base_studios
        mock_base_studio_cls.return_value = mock_instance

        with patch("lightning_sdk.cli.base_studio.list.click.echo") as mock_echo:
            list_impl(include_disabled=False)

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


def test_list_excludes_disabled_by_default():
    """Test that disabled base studios are excluded by default."""
    from unittest.mock import Mock, patch

    from lightning_sdk.base_studio import BaseStudioInfo
    from lightning_sdk.cli.base_studio.list import list_impl

    enabled_studios = [
        BaseStudioInfo(
            id="1",
            name="Enabled Studio",
            managed_id="managed-1",
            description="This is enabled",
            creator="⚡ Lightning AI",
            enabled=True,
        ),
    ]

    with patch("lightning_sdk.cli.base_studio.list.BaseStudio") as mock_base_studio_cls:
        mock_instance = Mock()
        mock_instance.list.return_value = enabled_studios
        mock_base_studio_cls.return_value = mock_instance

        with patch("lightning_sdk.cli.base_studio.list.click.echo") as mock_echo:
            list_impl(include_disabled=False)

            calls = mock_instance.list.call_args_list
            assert len(calls) == 1
            assert calls[0][1]["include_disabled"] is False

            echo_call_args = mock_echo.call_args[0][0]
            assert "enabled-studio" in echo_call_args


def test_list_includes_disabled_when_flag_set():
    """Test that disabled base studios are included when --include-disabled flag is set."""
    from unittest.mock import Mock, patch

    from lightning_sdk.base_studio import BaseStudioInfo
    from lightning_sdk.cli.base_studio.list import list_impl

    all_studios = [
        BaseStudioInfo(
            id="1",
            name="Enabled Studio",
            managed_id="managed-1",
            description="This is enabled",
            creator="⚡ Lightning AI",
            enabled=True,
        ),
        BaseStudioInfo(
            id="2",
            name="Disabled Studio",
            managed_id="managed-2",
            description="This is disabled",
            creator="⚡ Lightning AI",
            enabled=False,
        ),
    ]

    with patch("lightning_sdk.cli.base_studio.list.BaseStudio") as mock_base_studio_cls:
        mock_instance = Mock()
        mock_instance.list.return_value = all_studios
        mock_base_studio_cls.return_value = mock_instance

        with patch("lightning_sdk.cli.base_studio.list.click.echo") as mock_echo:
            list_impl(include_disabled=True)

            calls = mock_instance.list.call_args_list
            assert len(calls) == 1
            assert calls[0][1]["include_disabled"] is True

            echo_call_args = mock_echo.call_args[0][0]
            assert "enabled-studio" in echo_call_args
            assert "disabled-studio" in echo_call_args


def test_list_displays_enabled_status():
    """Test that the enabled status is correctly displayed as Yes/No."""
    from unittest.mock import Mock, patch

    from lightning_sdk.base_studio import BaseStudioInfo
    from lightning_sdk.cli.base_studio.list import list_impl

    studios_with_status = [
        BaseStudioInfo(
            id="1",
            name="Enabled",
            managed_id="managed-1",
            description="Enabled studio",
            creator="⚡ Lightning AI",
            enabled=True,
        ),
        BaseStudioInfo(
            id="2",
            name="Disabled",
            managed_id="managed-2",
            description="Disabled studio",
            creator="⚡ Lightning AI",
            enabled=False,
        ),
    ]

    with patch("lightning_sdk.cli.base_studio.list.BaseStudio") as mock_base_studio_cls:
        mock_instance = Mock()
        mock_instance.list.return_value = studios_with_status
        mock_base_studio_cls.return_value = mock_instance

        with patch("lightning_sdk.cli.base_studio.list.click.echo") as mock_echo:
            list_impl(include_disabled=True)

            echo_call_args = mock_echo.call_args[0][0]

            assert "Yes" in echo_call_args
            assert "No" in echo_call_args
            assert "Enabled" in echo_call_args


def test_list_displays_creator_for_managed_studios():
    """Test that managed studios display '⚡ Lightning AI' as creator."""
    from unittest.mock import Mock, patch

    from lightning_sdk.base_studio import BaseStudioInfo
    from lightning_sdk.cli.base_studio.list import list_impl

    managed_studios = [
        BaseStudioInfo(
            id="1",
            name="Managed Studio 1",
            managed_id="lightning-managed-1",
            description="First managed studio",
            creator="⚡ Lightning AI",
            enabled=True,
        ),
        BaseStudioInfo(
            id="2",
            name="Managed Studio 2",
            managed_id="lightning-managed-2",
            description="Second managed studio",
            creator="⚡ Lightning AI",
            enabled=True,
        ),
    ]

    with patch("lightning_sdk.cli.base_studio.list.BaseStudio") as mock_base_studio_cls:
        mock_instance = Mock()
        mock_instance.list.return_value = managed_studios
        mock_base_studio_cls.return_value = mock_instance

        with patch("lightning_sdk.cli.base_studio.list.click.echo") as mock_echo:
            list_impl(include_disabled=False)

            echo_call_args = mock_echo.call_args[0][0]

            assert "Creator" in echo_call_args
            assert "⚡ Lightning AI" in echo_call_args


def test_list_displays_creator_for_custom_studios():
    """Test that custom studios display the username as creator."""
    from unittest.mock import Mock, patch

    from lightning_sdk.base_studio import BaseStudioInfo
    from lightning_sdk.cli.base_studio.list import list_impl

    custom_studios = [
        BaseStudioInfo(
            id="1",
            name="Custom Studio 1",
            managed_id="",
            description="User created studio",
            creator="fake_user",
            enabled=True,
        ),
        BaseStudioInfo(
            id="2",
            name="Custom Studio 2",
            managed_id=None,
            description="Another user studio",
            creator="other_user",
            enabled=True,
        ),
    ]

    with patch("lightning_sdk.cli.base_studio.list.BaseStudio") as mock_base_studio_cls:
        mock_instance = Mock()
        mock_instance.list.return_value = custom_studios
        mock_base_studio_cls.return_value = mock_instance

        with patch("lightning_sdk.cli.base_studio.list.click.echo") as mock_echo:
            list_impl(include_disabled=False)

            echo_call_args = mock_echo.call_args[0][0]

            assert "fake_user" in echo_call_args
            assert "other_user" in echo_call_args


def test_list_displays_mixed_creators():
    """Test that both managed and custom studios display correct creators."""
    from unittest.mock import Mock, patch

    from lightning_sdk.base_studio import BaseStudioInfo
    from lightning_sdk.cli.base_studio.list import list_impl

    studios = [
        BaseStudioInfo(
            id="1",
            name="Managed",
            managed_id="lightning-1",
            description="Managed by Lightning",
            creator="⚡ Lightning AI",
            enabled=True,
        ),
        BaseStudioInfo(
            id="2",
            name="Custom",
            managed_id="",
            description="Custom studio",
            creator="developer",
            enabled=True,
        ),
    ]

    with patch("lightning_sdk.cli.base_studio.list.BaseStudio") as mock_base_studio_cls:
        mock_instance = Mock()
        mock_instance.list.return_value = studios
        mock_base_studio_cls.return_value = mock_instance

        with patch("lightning_sdk.cli.base_studio.list.click.echo") as mock_echo:
            list_impl(include_disabled=False)

            echo_call_args = mock_echo.call_args[0][0]

            assert "⚡ Lightning AI" in echo_call_args
            assert "developer" in echo_call_args
            assert "Creator" in echo_call_args  # Column header
