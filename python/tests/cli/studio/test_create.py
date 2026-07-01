from tests.cli.help import assert_help_contains, command_text


def test_create_studio():
    result_text = command_text("lightning studio create --help")

    assert "Usage: lightning studio create [OPTIONS]" in result_text
    assert "Create a new Studio." in result_text
    assert "--name" in result_text
    assert "--teamspace" in result_text
    assert "--cloud" in result_text
    assert "--cloud-provider" not in result_text
    assert "--cloud-account" not in result_text
    assert "--studio-type" in result_text


def test_studios_create_help() -> None:
    assert_help_contains("lightning studios create --help", "Usage: lightning studios create", "Create a new Studio.")


def test_create_help() -> None:
    text = assert_help_contains(
        "lightning create --help",
        "`lightning create` has moved to noun-first commands:",
        "studio -> lightning studio create",
    )
    assert "Deprecation warning:" not in text


def test_create_studio_legacy_help() -> None:
    assert_help_contains(
        "lightning create studio --help",
        "Deprecation warning:",
        "Use `lightning studio create` instead of `lightning create studio`.",
        "Usage: lightning create studio [OPTIONS]",
    )


def test_create_studio_with_studio_type(monkeypatch):
    """Test that --studio-type option is passed to get_base_studio_id."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.create import create_studio

    runner = CliRunner()

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)
    mock_studio_class.__qualname__ = "Studio"

    mock_get_base_studio_id = MagicMock(return_value="template-id-123")

    with patch("lightning_sdk.cli.studio.create.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.create.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.create.get_base_studio_id", mock_get_base_studio_id), patch(
        "lightning_sdk.cli.studio.create.Studio", mock_studio_class
    ):
        result = runner.invoke(create_studio, ["--name", "test-studio", "--studio-type", "python-template"])

        if result.exit_code != 0:
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
            if result.exception:
                raise result.exception

        mock_get_base_studio_id.assert_called_once_with("python-template", teamspace="owner/teamspace")

        mock_studio_class.assert_called_once()
        call_kwargs = mock_studio_class.call_args[1]
        assert call_kwargs["studio_type"] == "template-id-123"


def test_create_studio_without_studio_type(monkeypatch):
    """Test that get_base_studio_id is called with None when --studio-type is not provided."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.create import create_studio

    runner = CliRunner()

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)
    mock_studio_class.__qualname__ = "Studio"

    mock_get_base_studio_id = MagicMock(return_value="default-template-id")

    with patch("lightning_sdk.cli.studio.create.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.create.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.create.get_base_studio_id", mock_get_base_studio_id), patch(
        "lightning_sdk.cli.studio.create.Studio", mock_studio_class
    ):
        runner.invoke(create_studio, ["--name", "test-studio"])

        mock_get_base_studio_id.assert_called_once_with(None, teamspace="owner/teamspace")

        mock_studio_class.assert_called_once()
        call_kwargs = mock_studio_class.call_args[1]
        assert call_kwargs["studio_type"] == "default-template-id"


def test_create_studio_with_cloud(monkeypatch):
    """Test that --cloud option is forwarded to Studio."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.create import create_studio

    runner = CliRunner()

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)
    mock_studio_class.__qualname__ = "Studio"

    with patch("lightning_sdk.cli.studio.create.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.create.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.create.get_base_studio_id", return_value="template-id"), patch(
        "lightning_sdk.cli.studio.create.Studio", mock_studio_class
    ):
        runner.invoke(create_studio, ["--name", "test-studio", "--cloud", "aws"])

        mock_studio_class.assert_called_once()
        call_kwargs = mock_studio_class.call_args[1]
        assert call_kwargs["cloud"] == "aws"


def test_create_studio_passes_correct_parameter_name():
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.create import create_studio

    runner = CliRunner()

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)
    mock_studio_class.__qualname__ = "Studio"

    with patch("lightning_sdk.cli.studio.create.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.create.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.create.get_base_studio_id", return_value="template-id-xyz"), patch(
        "lightning_sdk.cli.studio.create.Studio", mock_studio_class
    ):
        result = runner.invoke(create_studio, ["--name", "test-studio", "--studio-type", "data-science"])

        if result.exit_code != 0:
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
            if result.exception:
                raise result.exception

        mock_studio_class.assert_called_once()
        call_kwargs = mock_studio_class.call_args[1]

        assert "studio_type" in call_kwargs, "studio_type parameter is missing"
        assert "template_id" not in call_kwargs, "template_id should not be passed (wrong parameter name)"
        assert call_kwargs["studio_type"] == "template-id-xyz"


def test_create_studio_with_all_options():
    """Test that all options are passed correctly to Studio constructor."""
    from unittest.mock import MagicMock, patch

    from lightning_sdk.cli.studio.create import create_impl

    mock_teamspace_menu = MagicMock()
    mock_resolved_teamspace = MagicMock()
    mock_teamspace_menu.return_value = mock_resolved_teamspace

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)
    mock_studio_class.__qualname__ = "Studio"

    mock_get_base_studio_id = MagicMock(return_value="ml-template")

    with patch("lightning_sdk.cli.studio.create.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.create.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.create.get_base_studio_id", mock_get_base_studio_id), patch(
        "lightning_sdk.cli.studio.create.Studio", mock_studio_class
    ):
        create_impl(
            name="my-studio",
            teamspace="owner/teamspace",
            cloud="my-cloud-account",
            vm=False,
            studio_type="machine-learning",
        )

        mock_get_base_studio_id.assert_called_once_with("machine-learning", teamspace=mock_resolved_teamspace)

        mock_studio_class.assert_called_once()
        call_kwargs = mock_studio_class.call_args[1]

        assert call_kwargs["name"] == "my-studio"
        assert call_kwargs["teamspace"] == mock_resolved_teamspace
        assert call_kwargs["create_ok"] is True
        assert call_kwargs["cloud"] == "my-cloud-account"
        assert call_kwargs["studio_type"] == "ml-template"
        assert "template_id" not in call_kwargs
