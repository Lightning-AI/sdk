import subprocess


def test_create_studio():
    result = subprocess.run("lightning studio create --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning studio create [OPTIONS]

  Create a new Studio.

  Example:     lightning studio create

Options:
  --name TEXT                     The name of the studio to create. If not
                                  provided, a random name will be generated.
  --teamspace TEXT                Override default teamspace (format:
                                  owner/teamspace)
  --cloud-provider [AWS|GCP|LAMBDA_LABS|DGX|VOLTAGE_PARK|NEBIUS|MACHINE|LIGHTNING]
                                  The cloud provider to start the studio on.
                                  Defaults to teamspace default.
  --cloud-account TEXT            The cloud account to create the studio on.
                                  Defaults to teamspace default.
  --studio-type TEXT              The base studio template name to use for
                                  creating the studio. Must be lowercase and
                                  hyphenated (use '-' instead of spaces). Run
                                  'lightning base-studio list' to see all
                                  available templates. Defaults to the first
                                  available template.
  --help                          Show this message and exit.
"""
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

        mock_get_base_studio_id.assert_called_once_with("python-template")

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

        mock_get_base_studio_id.assert_called_once_with(None)

        mock_studio_class.assert_called_once()
        call_kwargs = mock_studio_class.call_args[1]
        assert call_kwargs["studio_type"] == "default-template-id"


def test_create_studio_with_cloud_provider(monkeypatch):
    """Test that --cloud-provider option works correctly."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.create import create_studio
    from lightning_sdk.machine import CloudProvider

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
        runner.invoke(create_studio, ["--name", "test-studio", "--cloud-provider", "AWS"])

        mock_studio_class.assert_called_once()
        call_kwargs = mock_studio_class.call_args[1]
        assert call_kwargs["cloud_provider"] == CloudProvider.AWS


def test_create_studio_with_cloud_account(monkeypatch):
    """Test that --cloud-account option works correctly."""
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
        runner.invoke(create_studio, ["--name", "test-studio", "--cloud-account", "my-account"])

        mock_studio_class.assert_called_once()
        call_kwargs = mock_studio_class.call_args[1]
        assert call_kwargs["cloud_account"] == "my-account"


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
    from lightning_sdk.machine import CloudProvider

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)
    mock_studio_class.__qualname__ = "Studio"

    with patch("lightning_sdk.cli.studio.create.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.create.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.create.get_base_studio_id", return_value="ml-template"), patch(
        "lightning_sdk.cli.studio.create.Studio", mock_studio_class
    ):
        create_impl(
            name="my-studio",
            teamspace="owner/teamspace",
            cloud_provider="AWS",
            cloud_account="my-cloud-account",
            vm=False,
            studio_type="machine-learning",
        )

        mock_studio_class.assert_called_once()
        call_kwargs = mock_studio_class.call_args[1]

        assert call_kwargs["name"] == "my-studio"
        assert call_kwargs["teamspace"] == "owner/teamspace"
        assert call_kwargs["create_ok"] is True
        assert call_kwargs["cloud_provider"] == CloudProvider.AWS
        assert call_kwargs["cloud_account"] == "my-cloud-account"
        assert call_kwargs["studio_type"] == "ml-template"
        assert "template_id" not in call_kwargs
