import subprocess

import pytest

from lightning_sdk.cli.studio.connect import (
    _construct_available_gpus,
    _get_machine_from_gpus,
    _split_gpus_spec,
)


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
  --cloud-provider [AWS|GCP|LAMBDA_LABS|DGX|VOLTAGE_PARK|NEBIUS|LIGHTNING]
                                  The cloud provider to start the studio on.
                                  Defaults to teamspace default.
  --cloud-account TEXT            The cloud account to create the studio on.
                                  Defaults to teamspace default.
  --machine [CPU_SMALL|CPU|CPU_X_2|CPU_X_4|CPU_X_8|CPU_X_16|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4|T4_X_2|T4_X_4|T4_X_8|L4|L4_X_2|L4_X_4|L4_X_8|L40S|L40S_X_2|L40S_X_4|L40S_X_8|A100|A100_X_2|A100_X_4|A100_X_8|H100|H100_X_2|H100_X_4|H100_X_8|H200|H200_X_8|B200_X_8]
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
  --help                          Show this message and exit.
"""  # noqa: E501
    )


def test_connect_studio_machine_and_gpus_mutually_exclusive(monkeypatch):
    """Test that providing both --machine and --gpus raises an error."""
    from unittest.mock import MagicMock, patch

    from click.testing import CliRunner

    from lightning_sdk.cli.studio.connect import connect_studio

    runner = CliRunner()

    # Mock all the dependencies
    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect._get_base_studio_id", return_value="template-id"), patch(
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

    # Mock all the dependencies
    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect._get_base_studio_id", return_value="template-id"), patch(
        "lightning_sdk.cli.studio.connect.Studio", mock_studio_class
    ), patch("lightning_sdk.cli.studio.connect.save_studio_to_config"), patch(
        "lightning_sdk.cli.studio.connect.configure_ssh_internal", return_value="/path/to/key"
    ), patch("subprocess.run"):
        runner.invoke(connect_studio, ["test-studio", "--gpus", "L4:4"])

        # Check that studio was started with correct machine type
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

    # Mock all the dependencies
    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "owner/teamspace"

    mock_studio_instance = MagicMock()
    mock_studio_instance._studio.id = "studio-123"
    mock_studio_class = MagicMock(return_value=mock_studio_instance)

    with patch("lightning_sdk.cli.studio.connect.TeamspacesMenu", return_value=mock_teamspace_menu), patch(
        "lightning_sdk.cli.studio.connect.save_teamspace_to_config"
    ), patch("lightning_sdk.cli.studio.connect._get_base_studio_id", return_value="template-id"), patch(
        "lightning_sdk.cli.studio.connect.Studio", mock_studio_class
    ), patch("lightning_sdk.cli.studio.connect.save_studio_to_config"), patch(
        "lightning_sdk.cli.studio.connect.configure_ssh_internal", return_value="/path/to/key"
    ), patch("subprocess.run"):
        runner.invoke(connect_studio, ["test-studio"])

        # Check that studio was started with default machine type
        mock_studio_instance.start.assert_called_once()
        call_kwargs = mock_studio_instance.start.call_args[1]
        assert call_kwargs["machine"] == "CPU"


def test_split_gpus_spec_valid():
    name, count = _split_gpus_spec("L4:4")
    assert name == "L4"
    assert isinstance(count, int)
    assert count == 4


def test_split_gpus_spec_trims_spaces():
    name, count = _split_gpus_spec("  L4  :  2  ")
    assert name == "L4"
    assert count == 2


@pytest.mark.parametrize("bad", ["L4:0", "L4:-1", "L4:foo"])
def test_split_gpus_spec_invalid_counts(bad):
    with pytest.raises(ValueError, match="Invalid GPU count"):
        _split_gpus_spec(bad)


def test_construct_available_gpus():
    machine_options = {"l4": "L4", "l4_x_4": "L4_X_4", "cpu": "CPU"}
    res = _construct_available_gpus(machine_options)
    assert set(res) == {"L4", "L4:4", "CPU"}


def test_get_machine_from_gpus_simple_and_with_count():
    # simple GPU type
    assert _get_machine_from_gpus("L4") == "L4"
    # explicit single GPU
    assert _get_machine_from_gpus("L4:1") == "L4"
    # multi GPU specification
    assert _get_machine_from_gpus("L4:4") == "L4_X_4"
    # case-insensitive input
    assert _get_machine_from_gpus("l4:2") == "L4_X_2"
    # other types
    assert _get_machine_from_gpus("A100:8") == "A100_X_8"


@pytest.mark.parametrize("bad", ["FOO:1", "UNKNOWN", "A100:999"])
def test_get_machine_from_gpus_invalid(bad):
    with pytest.raises(ValueError, match="Invalid GPU"):
        _get_machine_from_gpus(bad)


def test_get_base_studio_id_no_templates(monkeypatch):
    """Test when no base studios are available."""
    from unittest.mock import MagicMock

    from lightning_sdk.cli.studio.connect import _get_base_studio_id

    mock_base_studio = MagicMock()
    mock_base_studio.list.return_value = []

    def mock_base_studio_init(*args, **kwargs):
        return mock_base_studio

    monkeypatch.setattr("lightning_sdk.cli.studio.connect.BaseStudio", mock_base_studio_init)

    result = _get_base_studio_id(None)
    assert result is None


def test_get_base_studio_id_default_first_template(monkeypatch):
    """Test that first template is used when studio_type is not specified."""
    from unittest.mock import MagicMock

    from lightning_sdk.cli.studio.connect import _get_base_studio_id

    mock_template_1 = MagicMock()
    mock_template_1.id = "template-id-1"
    mock_template_1.name = "Python Template"

    mock_template_2 = MagicMock()
    mock_template_2.id = "template-id-2"
    mock_template_2.name = "Data Science Template"

    mock_base_studio = MagicMock()
    mock_base_studio.list.return_value = [mock_template_1, mock_template_2]

    def mock_base_studio_init(*args, **kwargs):
        return mock_base_studio

    monkeypatch.setattr("lightning_sdk.cli.studio.connect.BaseStudio", mock_base_studio_init)

    result = _get_base_studio_id(None)
    assert result == "template-id-1"


def test_get_base_studio_id_matches_studio_type(monkeypatch):
    """Test that correct template is selected when studio_type matches."""
    from unittest.mock import MagicMock

    from lightning_sdk.cli.studio.connect import _get_base_studio_id

    mock_template_1 = MagicMock()
    mock_template_1.id = "template-id-1"
    mock_template_1.name = "Python Template"

    mock_template_2 = MagicMock()
    mock_template_2.id = "template-id-2"
    mock_template_2.name = "Data Science Template"

    mock_base_studio = MagicMock()
    mock_base_studio.list.return_value = [mock_template_1, mock_template_2]

    def mock_base_studio_init(*args, **kwargs):
        return mock_base_studio

    monkeypatch.setattr("lightning_sdk.cli.studio.connect.BaseStudio", mock_base_studio_init)

    # Test with hyphenated name matching
    result = _get_base_studio_id("data-science-template")
    assert result == "template-id-2"

    # Test case insensitivity
    result = _get_base_studio_id("DATA-SCIENCE TEMPLATE")
    assert result == "template-id-2"


def test_get_base_studio_id_no_match_uses_first(monkeypatch):
    """Test that first template is used when studio_type doesn't match any."""
    from unittest.mock import MagicMock

    from lightning_sdk.cli.studio.connect import _get_base_studio_id

    mock_template_1 = MagicMock()
    mock_template_1.id = "template-id-1"
    mock_template_1.name = "Python Template"

    mock_base_studio = MagicMock()
    mock_base_studio.list.return_value = [mock_template_1]

    def mock_base_studio_init(*args, **kwargs):
        return mock_base_studio

    monkeypatch.setattr("lightning_sdk.cli.studio.connect.BaseStudio", mock_base_studio_init)

    result = _get_base_studio_id("nonexistent-template")
    assert result == "template-id-1"
