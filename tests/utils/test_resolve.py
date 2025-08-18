import os
import tempfile
from unittest import mock

import pytest
import yaml

from lightning_sdk.models import _parse_org_teamspace_model_version
from lightning_sdk.organization import Organization
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import (
    _get_studio_url,
    _parse_model_and_version,
    _resolve_org,
    _resolve_org_name,
    _resolve_teamspace,
    _resolve_teamspace_name,
    _resolve_user,
    _resolve_user_name,
)


@pytest.mark.parametrize("provided", [None, "abc"])
@mock.patch.dict(os.environ, clear=True)
def test_resolve_org_name_no_env_var(provided):
    with mock.patch("lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", "/nonexistent/config.yaml"):
        result = _resolve_org_name(provided)

        if provided is None:
            assert result is None
        else:
            assert result == provided


@pytest.mark.parametrize("provided", [None, "abc", "def"])
@mock.patch.dict(
    os.environ,
    {
        "LIGHTNING_ORG": "abc",
    },
)
def test_resolve_org_name_env_var(provided):
    result = _resolve_org_name(provided)

    if provided is None:
        assert result == "abc"
    else:
        assert result == provided


@pytest.mark.parametrize("provided", [None, "abc", "def"])
@mock.patch.dict(
    os.environ,
    {
        "LIGHTNING_ORG": "",
    },
)
def test_resolve_org_name_empty_env_var(provided):
    result = _resolve_org_name(provided)

    if provided is None:
        assert result is None
    else:
        assert result == provided


@pytest.mark.parametrize("provided", [None, "org_name", -1])
@mock.patch.dict(os.environ, clear=True)
def test_resolve_org(internal_get_org_api_mocker, provided):
    # can't instantiate outside without proper mocking
    if provided == -1:
        provided = Organization(name="org_name")

    result = _resolve_org(provided)

    if provided is None:
        assert result is None
    elif isinstance(provided, Organization):
        assert result == provided
    else:
        assert isinstance(result, Organization)
        assert result.name == provided


@mock.patch.dict(os.environ, clear=True)
def test_resolve_org_with_user(internal_get_org_api_mocker):
    name = "user-name"
    with pytest.raises(ValueError, match=f"Organization '{name}' does not exist or you are not a member of it."):
        _resolve_org(name)


@pytest.mark.parametrize("provided", [None, "abc"])
@mock.patch.dict(os.environ, clear=True)
def test_resolve_user_name_no_env_var(provided):
    with mock.patch("lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", "/nonexistent/config.yaml"):
        result = _resolve_user_name(provided)

        if provided is None:
            assert result is None
        else:
            assert result == provided


@pytest.mark.parametrize("provided", [None, "abc", "def"])
@mock.patch.dict(
    os.environ,
    {
        "LIGHTNING_USERNAME": "abc",
    },
)
def test_resolve_user_name_env_var(provided):
    result = _resolve_user_name(provided)

    if provided is None:
        assert result == "abc"
    else:
        assert result == provided


@pytest.mark.parametrize("provided", [None, "user_name", -1])
@mock.patch.dict(os.environ, clear=True)
def test_resolve_user(internal_user_api_mocker, provided):
    # can't instantiate outside without proper mocking
    if provided == -1:
        provided = User(name="user_name")

    result = _resolve_user(provided)

    if provided is None:
        assert result is None
    elif isinstance(provided, User):
        assert result == provided
    else:
        assert isinstance(result, User)
        assert result.name == provided


@pytest.mark.parametrize("provided", [None, "abc"])
@mock.patch.dict(os.environ, clear=True)
def test_resolve_teamspace_name_no_env_var(provided):
    with mock.patch("lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", "/nonexistent/config.yaml"):
        result = _resolve_teamspace_name(provided)

        if provided is None:
            assert result is None
        else:
            assert result == provided


@pytest.mark.parametrize("provided", [None, "abc", "def"])
@mock.patch.dict(
    os.environ,
    {
        "LIGHTNING_TEAMSPACE": "abc",
    },
)
def test_resolve_teamspace_name_env_var(provided):
    result = _resolve_teamspace_name(provided)

    if provided is None:
        assert result == "abc"
    else:
        assert result == provided


@pytest.mark.parametrize(
    ("teamspace_name", "org_name", "user_name", "expected_result"),
    [
        ("ts-abc", None, "user-abc", {"name": "ts-abc", "user": {"name": "user-abc"}}),
        ("ts-def", "org-abc", None, {"name": "ts-def", "org": {"name": "org-abc"}}),
    ],
)
def test_resolve_teamspace_combinations(
    internal_user_api_mocker,
    internal_get_org_api_mocker,
    resolve_all_teamspaces_api_mocker,
    teamspace_name,
    org_name,
    user_name,
    expected_result,
):
    org_env_var_value = org_name if org_name is not None else ""
    user_env_var_value = user_name if user_name is not None else ""

    with mock.patch.dict(
        os.environ,
        {
            "LIGHTNING_ORG": org_env_var_value,
            "LIGHTNING_USERNAME": user_env_var_value,
            "LIGHTNING_TEAMSPACE": teamspace_name,
        },
        clear=True,
    ):
        result = _resolve_teamspace(None, org_name, user_name)

        assert isinstance(result, Teamspace)

        expected_org = expected_result.get("org", {})
        expected_org_name = expected_org.get("name", None)
        expected_user = expected_result.get("user", {})
        expected_user_name = expected_user.get("name", None)

        print(expected_org_name, expected_user_name)

        assert result == Teamspace(
            teamspace_name, org=_resolve_org(expected_org_name), user=_resolve_user(expected_user_name)
        )


def test_parse_model_and_version():
    # Most of the validation for name and version happens in the backend
    assert _parse_model_and_version("") == ("", None)
    assert _parse_model_and_version("user/modelname") == ("user/modelname", None)
    assert _parse_model_and_version("user/modelname:") == ("user/modelname", "")
    assert _parse_model_and_version("user/modelname:v1") == ("user/modelname", "v1")
    assert _parse_model_and_version("user/modelname: v1") == ("user/modelname", " v1")
    with pytest.raises(ValueError, match="Model version is expected to be in the format"):
        _parse_model_and_version("user/modelname:v1:")
    with pytest.raises(ValueError, match="Model version is expected to be in the format"):
        _parse_model_and_version("user/modelname:v1:v2")


@mock.patch.dict(os.environ, {}, clear=True)
def test_resolve_org_name_with_config_defaults():
    """Test _resolve_org_name uses config defaults when env var is not set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config_data = {"organization": {"name": "config-org"}}

        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)

        with mock.patch("lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", config_path):
            result = _resolve_org_name(None)
            assert result == "config-org"


@mock.patch.dict(os.environ, {"LIGHTNING_ORG": "env-org"}, clear=True)
def test_resolve_org_name_env_overrides_config():
    """Test _resolve_org_name uses env var over config defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config_data = {"organization": {"name": "config-org"}}

        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)

        with mock.patch("lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", config_path):
            result = _resolve_org_name(None)
            assert result == "env-org"


def test_resolve_org_name_explicit_overrides_all():
    """Test _resolve_org_name uses explicit value over env and config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config_data = {"organization": {"name": "config-org"}}

        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)

        with mock.patch.dict(os.environ, {"LIGHTNING_ORG": "env-org"}), mock.patch(
            "lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", config_path
        ):
            result = _resolve_org_name("explicit-org")
            assert result == "explicit-org"


@mock.patch.dict(os.environ, {}, clear=True)
def test_resolve_teamspace_name_with_config_defaults():
    """Test _resolve_teamspace_name uses config defaults when env var is not set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config_data = {"teamspace": {"name": "config-teamspace"}}

        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)

        with mock.patch("lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", config_path):
            result = _resolve_teamspace_name(None)
            assert result == "config-teamspace"


@mock.patch.dict(os.environ, {"LIGHTNING_TEAMSPACE": "env-teamspace"}, clear=True)
def test_resolve_teamspace_name_env_overrides_config():
    """Test _resolve_teamspace_name uses env var over config defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config_data = {"teamspace": {"name": "config-teamspace"}}

        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)

        with mock.patch("lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", config_path):
            result = _resolve_teamspace_name(None)
            assert result == "env-teamspace"


@mock.patch.dict(os.environ, {}, clear=True)
def test_config_teamspace_owner_type_organization():
    """Test config provides org ownership type and name correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config_data = {"teamspace": {"name": "config-teamspace", "owner": "config-org", "owner_type": "organization"}}

        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)

        with mock.patch("lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", config_path):
            from lightning_sdk.utils.config import Config, DefaultConfigKeys

            config = Config()

            assert config.get_value(DefaultConfigKeys.teamspace_owner_type) == "organization"
            assert config.get_value(DefaultConfigKeys.teamspace_owner) == "config-org"
            assert config.get_value(DefaultConfigKeys.teamspace_name) == "config-teamspace"


@mock.patch.dict(os.environ, {}, clear=True)
def test_config_teamspace_owner_type_user():
    """Test config provides user ownership type and name correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config_data = {"teamspace": {"name": "config-teamspace", "owner": "config-user", "owner_type": "user"}}

        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)

        with mock.patch("lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", config_path):
            from lightning_sdk.utils.config import Config, DefaultConfigKeys

            config = Config()

            assert config.get_value(DefaultConfigKeys.teamspace_owner_type) == "user"
            assert config.get_value(DefaultConfigKeys.teamspace_owner) == "config-user"
            assert config.get_value(DefaultConfigKeys.teamspace_name) == "config-teamspace"


@mock.patch.dict(os.environ, {}, clear=True)
def test_resolve_user_name_with_config_defaults():
    """Test _resolve_user_name uses config defaults when env var is not set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config_data = {"user": {"name": "config-user"}}

        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)

        with mock.patch("lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", config_path):
            result = _resolve_user_name(None)
            assert result == "config-user"


@mock.patch.dict(os.environ, {"LIGHTNING_USERNAME": "env-user"}, clear=True)
def test_resolve_user_name_env_overrides_config():
    """Test _resolve_user_name uses env var over config defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config_data = {"user": {"name": "config-user"}}

        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)

        with mock.patch("lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", config_path):
            result = _resolve_user_name(None)
            assert result == "env-user"


def test_resolve_user_name_explicit_overrides_all():
    """Test _resolve_user_name uses explicit value over env and config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config_data = {"user": {"name": "config-user"}}

        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)

        with mock.patch.dict(os.environ, {"LIGHTNING_USERNAME": "env-user"}), mock.patch(
            "lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", config_path
        ):
            result = _resolve_user_name("explicit-user")
            assert result == "explicit-user"


def test_parse_model_name_and_version():
    assert _parse_org_teamspace_model_version("org/teamspace/model") == ("org", "teamspace", "model", None)
    assert _parse_org_teamspace_model_version("org/teamspace/model:v1") == ("org", "teamspace", "model", "v1")
    with pytest.raises(
        ValueError, match="Model version is expected to be in the format `organization/teamspace/model_name:version`"
    ):
        _parse_org_teamspace_model_version("org/teamspace/model:v1:v2")
    with pytest.raises(ValueError, match="Model name must be in the format `organization/teamspace/model_name`"):
        _parse_org_teamspace_model_version("org_teamspace/model:v1")


@mock.patch.dict(os.environ, {"LIGHTNING_CLOUD_URL": "lightning.ai:443"}, clear=True)
def test_get_studio_url(internal_studio_init_mocker):
    studio = Studio("st-abc", "ts-abc", org="org-abc")

    url = _get_studio_url(studio)

    assert url == "lightning.ai/org-abc/ts-abc/studios/st-abc/code"


@mock.patch.dict(os.environ, {"LIGHTNING_CLOUD_URL": "lightning.ai:443"}, clear=True)
def test_get_studio_url_turn_on(internal_studio_init_mocker):
    studio = Studio("st-abc", "ts-abc", org="org-abc")

    url = _get_studio_url(studio, turn_on=True)

    assert url == "lightning.ai/org-abc/ts-abc/studios/st-abc/code?turnOn=true"
