import subprocess


def test_connect_studio():
    result = subprocess.run("lightning studio connect --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning studio connect [OPTIONS] [NAME]

  Connect to a Studio.

  Example:     lightning studio connect

Options:
  --teamspace TEXT                Override default teamspace (format:
                                  owner/teamspace)
  --cloud-provider [AWS|GCP|LAMBDA_LABS|DGX|VOLTAGE_PARK|NEBIUS|MACHINE|LIGHTNING]
                                  The cloud provider to start the studio on.
                                  Defaults to teamspace default.
  --cloud-account TEXT            The cloud account to create the studio on.
                                  Defaults to teamspace default.
  --machine [CPU_SMALL|CPU|CPU_X_2|CPU_X_4|CPU_X_8|CPU_X_16|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4_SMALL|T4|T4_X_2|T4_X_4|T4_X_8|L4|L4_X_2|L4_X_4|L4_X_8|L40S|L40S_X_2|L40S_X_4|L40S_X_8|A100|A100_X_2|A100_X_4|A100_X_8|H100|H100_X_2|H100_X_4|H100_X_8|H200|H200_X_8|B200_X_8]
                                  The machine type to start the studio on.
                                  Defaults to CPU-4
  --gpus TEXT                     The number and type of GPUs to start the
                                  studio on (format: TYPE:COUNT, e.g. L4:4)
  --studio-type TEXT              The base studio template name to use for
                                  creating the studio. Must be lowercase and
                                  hyphenated (use '-' instead of spaces). Run
                                  'lightning base-studio list' to see all
                                  available templates. Defaults to the first
                                  available template.
  --interruptible                 Start the studio on an interruptible
                                  instance.
  --help                          Show this message and exit.
"""  # noqa: E501
    )


def test_connect_studio_machine_and_gpus_mutually_exclusive(monkeypatch):
    """Test that providing both --machine and --gpus raises an error."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.connect import connect_studio

    runner = CliRunner()

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value="template-id"), patch(
        "lightning_sdk.cli.studio.connect.Studio"
    ), patch("lightning_sdk.cli.studio.connect.save_studio_to_config"), patch(
        "lightning_sdk.cli.studio.connect.configure_ssh_internal"
    ), patch("subprocess.run"):
        result = runner.invoke(connect_studio, ["--machine", "L4", "--gpus", "L4:2"])
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output.lower()


def test_connect_studio_with_gpus_option(monkeypatch):
    """Test that --gpus option correctly converts to machine type."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.connect import connect_studio

    runner = CliRunner()

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value="template-id"), patch(
        "lightning_sdk.cli.studio.connect.Studio", mock_studio_class
    ), patch("lightning_sdk.cli.studio.connect.save_studio_to_config"), patch(
        "lightning_sdk.cli.studio.connect.configure_ssh_internal", return_value="/path/to/key"
    ), patch("subprocess.run"):
        runner.invoke(connect_studio, ["test-studio", "--gpus", "L4:4"])

        mock_studio_instance.start.assert_called_once()
        call_kwargs = mock_studio_instance.start.call_args[1]
        assert call_kwargs["machine"] == "L4_X_4"
        assert call_kwargs["interruptible"] is False


def test_connect_studio_uses_default_machine(monkeypatch):
    """Test that default machine (CPU) is used when neither --machine nor --gpus is provided."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.connect import connect_studio

    runner = CliRunner()

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"

    # Make Studio() constructor raise ValueError so it doesn't use studio context defaults
    def studio_side_effect(*args, **kwargs):
        if len(args) == 0 and len(kwargs) == 0:
            raise ValueError("No current studio")
        return mock_studio_instance

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value="template-id"), patch(
        "lightning_sdk.cli.studio.connect.Studio", side_effect=studio_side_effect
    ), patch("lightning_sdk.cli.studio.connect.save_studio_to_config"), patch(
        "lightning_sdk.cli.studio.connect.configure_ssh_internal", return_value="/path/to/key"
    ), patch("subprocess.run"):
        runner.invoke(connect_studio, ["test-studio"])

        mock_studio_instance.start.assert_called_once()
        call_kwargs = mock_studio_instance.start.call_args[1]
        assert call_kwargs["machine"] == "CPU"


def test_connect_studio_with_interruptible_flag(monkeypatch):
    """Test that --interruptible flag sets interruptible=True."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.connect import connect_studio

    runner = CliRunner()

    # Mock all the dependencies
    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value="template-id"), patch(
        "lightning_sdk.cli.studio.connect.Studio", mock_studio_class
    ), patch("lightning_sdk.cli.studio.connect.save_studio_to_config"), patch(
        "lightning_sdk.cli.studio.connect.configure_ssh_internal", return_value="/path/to/key"
    ), patch("subprocess.run"):
        runner.invoke(connect_studio, ["test-studio", "--interruptible"])

        mock_studio_instance.start.assert_called_once()
        call_kwargs = mock_studio_instance.start.call_args[1]
        assert call_kwargs["interruptible"] is True


def test_connect_studio_without_interruptible_flag(monkeypatch):
    """Test that interruptible defaults to False when flag is not provided."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.connect import connect_studio

    runner = CliRunner()

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value="template-id"), patch(
        "lightning_sdk.cli.studio.connect.Studio", mock_studio_class
    ), patch("lightning_sdk.cli.studio.connect.save_studio_to_config"), patch(
        "lightning_sdk.cli.studio.connect.configure_ssh_internal", return_value="/path/to/key"
    ), patch("subprocess.run"):
        runner.invoke(connect_studio, ["test-studio"])

        mock_studio_instance.start.assert_called_once()
        call_kwargs = mock_studio_instance.start.call_args[1]
        assert call_kwargs["interruptible"] is False


def test_connect_studio_interruptible_with_machine(monkeypatch):
    """Test that --interruptible works correctly with --machine option."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.connect import connect_studio
    from lightning_sdk.machine import Machine

    runner = CliRunner()

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value="template-id"), patch(
        "lightning_sdk.cli.studio.connect.Studio", mock_studio_class
    ), patch("lightning_sdk.cli.studio.connect.save_studio_to_config"), patch(
        "lightning_sdk.cli.studio.connect.configure_ssh_internal", return_value="/path/to/key"
    ), patch("subprocess.run"):
        runner.invoke(
            connect_studio,
            ["test-studio", "--interruptible"],
            catch_exceptions=False,
            obj={"machine": Machine.L4},
        )

        mock_studio_instance.start.assert_called_once()
        call_kwargs = mock_studio_instance.start.call_args[1]
        assert call_kwargs["interruptible"] is True


def test_connect_studio_interruptible_with_gpus(monkeypatch):
    """Test that --interruptible works correctly with --gpus option."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.connect import connect_studio

    runner = CliRunner()

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value="template-id"), patch(
        "lightning_sdk.cli.studio.connect.Studio", mock_studio_class
    ), patch("lightning_sdk.cli.studio.connect.save_studio_to_config"), patch(
        "lightning_sdk.cli.studio.connect.configure_ssh_internal", return_value="/path/to/key"
    ), patch("subprocess.run"):
        runner.invoke(connect_studio, ["test-studio", "--gpus", "A100:2", "--interruptible"])

        mock_studio_instance.start.assert_called_once()
        call_kwargs = mock_studio_instance.start.call_args[1]
        assert call_kwargs["machine"] == "A100_X_2"
        assert call_kwargs["interruptible"] is True


def test_parse_args_or_get_from_current_studio_all_args_provided(monkeypatch):
    """Test when all arguments are provided by user."""
    from unittest.mock import MagicMock, patch

    from lightning_sdk.cli.studio.connect import _parse_args_or_get_from_current_studio

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "resolved-owner/resolved-teamspace"

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value="template-123"), patch(
        "lightning_sdk.cli.studio.connect.random_unique_name", return_value="random-name"
    ):
        teamspace, cloud_account, template_id, machine, cloud_provider, name = _parse_args_or_get_from_current_studio(
            teamspace="owner/teamspace",
            cloud_account="account-123",
            studio_type="python-template",
            machine="L4",
            gpus=None,
            cloud_provider="AWS",
            name="my-studio",
        )

        assert teamspace == "resolved-owner/resolved-teamspace"
        assert cloud_account == "account-123"
        assert template_id == "template-123"
        assert machine == "L4"
        assert cloud_provider.value == "AWS"
        assert name == "my-studio"


def test_parse_args_or_get_from_current_studio_falls_back_to_current_studio(monkeypatch):
    """Test that missing args fall back to current studio context."""
    from unittest.mock import MagicMock, patch

    from lightning_sdk.cli.studio.connect import _parse_args_or_get_from_current_studio

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "menu-owner/menu-teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance.teamspace = "studio-owner/studio-teamspace"
    mock_studio_instance.cloud_account = "studio-cloud-account"
    mock_studio_instance._studio.environment_template_id = "studio-template-id"
    mock_studio_instance.machine = "A100"

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value=None), patch(
        "lightning_sdk.cli.studio.connect.Studio", return_value=mock_studio_instance
    ), patch("lightning_sdk.cli.studio.connect.random_unique_name", return_value="random-name"):
        teamspace, cloud_account, template_id, machine, cloud_provider, name = _parse_args_or_get_from_current_studio(
            teamspace=None,
            cloud_account=None,
            studio_type=None,
            machine=None,
            gpus=None,
            cloud_provider=None,
            name=None,
        )

        assert teamspace == "studio-owner/studio-teamspace"
        assert cloud_account == "studio-cloud-account"
        assert template_id == "studio-template-id"
        assert machine == "A100"
        assert cloud_provider is None
        assert name == "random-name"


def test_parse_args_or_get_from_current_studio_no_current_studio(monkeypatch):
    """Test when there is no current studio context (ValueError raised)."""
    from unittest.mock import MagicMock, patch

    from lightning_sdk.cli.studio.connect import _parse_args_or_get_from_current_studio

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "resolved-owner/resolved-teamspace"

    def mock_studio_init(*args, **kwargs):
        raise ValueError("No current studio")

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value="template-123"), patch(
        "lightning_sdk.cli.studio.connect.Studio", side_effect=mock_studio_init
    ), patch("lightning_sdk.cli.studio.connect.random_unique_name", return_value="random-name"):
        teamspace, cloud_account, template_id, machine, cloud_provider, name = _parse_args_or_get_from_current_studio(
            teamspace="owner/teamspace",
            cloud_account="account-123",
            studio_type="python-template",
            machine="L4",
            gpus=None,
            cloud_provider=None,
            name="my-studio",
        )

        assert teamspace == "resolved-owner/resolved-teamspace"
        assert cloud_account == "account-123"
        assert template_id == "template-123"
        assert machine == "L4"
        assert cloud_provider is None
        assert name == "my-studio"


def test_parse_args_or_get_from_current_studio_gpus_preserves_machine(monkeypatch):
    """Test that when gpus is provided, machine from studio context is not used."""
    from unittest.mock import MagicMock, patch

    from lightning_sdk.cli.studio.connect import _parse_args_or_get_from_current_studio

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance.teamspace = "studio-owner/studio-teamspace"
    mock_studio_instance.cloud_account = "studio-cloud-account"
    mock_studio_instance._studio.environment_template_id = "studio-template-id"
    mock_studio_instance.machine = "A100"

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value=None), patch(
        "lightning_sdk.cli.studio.connect.Studio", return_value=mock_studio_instance
    ), patch("lightning_sdk.cli.studio.connect.random_unique_name", return_value="random-name"):
        teamspace, cloud_account, template_id, machine, cloud_provider, name = _parse_args_or_get_from_current_studio(
            teamspace=None,
            cloud_account=None,
            studio_type=None,
            machine=None,
            gpus="L4:4",
            cloud_provider=None,
            name=None,
        )

        assert teamspace == "studio-owner/studio-teamspace"
        assert cloud_account == "studio-cloud-account"
        assert template_id == "studio-template-id"
        assert machine is None
        assert cloud_provider is None
        assert name == "random-name"


def test_parse_args_or_get_from_current_studio_cloud_provider_conversion(monkeypatch):
    """Test that cloud_provider string is converted to CloudProvider enum."""
    from unittest.mock import MagicMock, patch

    from lightning_sdk.cli.studio.connect import _parse_args_or_get_from_current_studio
    from lightning_sdk.machine import CloudProvider

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value="template-123"), patch(
        "lightning_sdk.cli.studio.connect.random_unique_name", return_value="random-name"
    ):
        for provider_str in ["AWS", "GCP", "LAMBDA_LABS"]:
            _, _, _, _, cloud_provider, _ = _parse_args_or_get_from_current_studio(
                teamspace="owner/teamspace",
                cloud_account=None,
                studio_type=None,
                machine="CPU",
                gpus=None,
                cloud_provider=provider_str,
                name="my-studio",
            )

            assert isinstance(cloud_provider, CloudProvider)
            assert cloud_provider.value == provider_str


def test_parse_args_or_get_from_current_studio_name_generation(monkeypatch):
    """Test that name is generated when not provided."""
    from unittest.mock import MagicMock, patch

    from lightning_sdk.cli.studio.connect import _parse_args_or_get_from_current_studio

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value="template-123"), patch(
        "lightning_sdk.cli.studio.connect.random_unique_name", return_value="generated-unique-name"
    ) as mock_random_name:
        _, _, _, _, _, name = _parse_args_or_get_from_current_studio(
            teamspace="owner/teamspace",
            cloud_account=None,
            studio_type=None,
            machine="CPU",
            gpus=None,
            cloud_provider=None,
            name=None,
        )

        assert name == "generated-unique-name"
        mock_random_name.assert_called_once()


def test_parse_args_or_get_from_current_studio_partial_args(monkeypatch):
    """Test with a mix of provided and missing arguments."""
    from unittest.mock import MagicMock, patch

    from lightning_sdk.cli.studio.connect import _parse_args_or_get_from_current_studio

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "resolved-teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance.teamspace = "studio-teamspace"
    mock_studio_instance.cloud_account = "studio-cloud-account"
    mock_studio_instance._studio.environment_template_id = "studio-template-id"
    mock_studio_instance.machine = "A100"

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect.get_base_studio_id", return_value="user-template-id"), patch(
        "lightning_sdk.cli.studio.connect.Studio", return_value=mock_studio_instance
    ), patch("lightning_sdk.cli.studio.connect.random_unique_name", return_value="random-name"):
        teamspace, cloud_account, template_id, machine, cloud_provider, name = _parse_args_or_get_from_current_studio(
            teamspace="user-teamspace",
            cloud_account=None,
            studio_type="user-template",
            machine="L4",
            gpus=None,
            cloud_provider=None,
            name=None,
        )

        assert teamspace == "resolved-teamspace"
        assert cloud_account == "studio-cloud-account"
        assert template_id == "user-template-id"
        assert machine == "L4"
        assert cloud_provider is None
        assert name == "random-name"
