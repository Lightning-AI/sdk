from unittest.mock import MagicMock, patch

import pytest
import rich_click as click

from lightning_sdk.cli.utils import teamspace_option
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace
from lightning_sdk.cli.utils.teamspace_option import teamspace_option as teamspace_option_decorator


def test_resolve_teamspace_delegates_to_cli_resolver():
    resolved = MagicMock()
    with patch.object(teamspace_option, "_resolve_cli_teamspace", return_value=resolved) as mock_resolve, patch.object(
        teamspace_option, "save_teamspace_to_config"
    ) as mock_save:
        assert resolve_teamspace(teamspace="owner/my-teamspace") is resolved
        mock_resolve.assert_called_once_with(teamspace="owner/my-teamspace", org=None, user=None)
        mock_save.assert_called_once_with(resolved, overwrite=False)


def test_resolve_teamspace_preserves_org_and_user_options():
    resolved = MagicMock()
    with patch.object(teamspace_option, "_resolve_cli_teamspace", return_value=resolved) as mock_resolve, patch.object(
        teamspace_option, "save_teamspace_to_config"
    ) as mock_save:
        assert resolve_teamspace(teamspace="my-teamspace", org="my-org") is resolved
        mock_resolve.assert_called_once_with(teamspace="my-teamspace", org="my-org", user=None)
        mock_save.assert_called_once_with(resolved, overwrite=False)


def test_slug_with_org_conflict_raises_usage_error():
    """An 'owner/teamspace' slug combined with --org/--user is ambiguous and must fail loudly."""
    with pytest.raises(click.UsageError, match="already specifies"):
        resolve_teamspace(teamspace="owner/my-teamspace", org="another-org")


def test_slug_with_user_conflict_raises_usage_error():
    with pytest.raises(click.UsageError, match="already specifies"):
        resolve_teamspace(teamspace="owner/my-teamspace", user="another-user")


def test_teamspace_option_adds_teamspace_org_user_params():
    @teamspace_option_decorator
    @click.command()
    def cmd(teamspace, org, user):
        pass

    names = {p.name for p in cmd.params}
    assert {"teamspace", "org", "user"} <= names


def test_teamspace_option_marks_org_and_user_deprecated_but_not_teamspace():
    @teamspace_option_decorator
    @click.command()
    def cmd(teamspace, org, user):
        pass

    params_by_name = {p.name: p for p in cmd.params}
    assert params_by_name["org"].deprecated
    assert params_by_name["user"].deprecated
    assert not params_by_name["teamspace"].deprecated
