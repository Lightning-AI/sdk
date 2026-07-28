from unittest.mock import MagicMock, patch

import pytest
import rich_click as click

from lightning_sdk.cli.utils import teamspace_option
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace
from lightning_sdk.cli.utils.teamspace_option import teamspace_option as teamspace_option_decorator


def test_bare_teamspace_uses_teamspaces_menu():
    """No --org/--user: resolution goes through TeamspacesMenu (slug + interactive fallback)."""
    resolved = MagicMock()
    with patch.object(teamspace_option, "TeamspacesMenu") as mock_menu_cls, patch.object(
        teamspace_option, "save_teamspace_to_config"
    ) as mock_save:
        mock_menu_cls.return_value.return_value = resolved
        assert resolve_teamspace(teamspace="owner/my-teamspace") is resolved
        mock_menu_cls.return_value.assert_called_once_with(teamspace="owner/my-teamspace")
        mock_save.assert_called_once_with(resolved, overwrite=False)


def test_org_or_user_path_calls_resolve_teamspace_directly():
    """--org/--user given: bypasses the menu, preserving today's exact behavior."""
    resolved = MagicMock()
    with patch.object(teamspace_option, "_resolve_teamspace", return_value=resolved) as mock_resolve, patch.object(
        teamspace_option, "save_teamspace_to_config"
    ) as mock_save:
        assert resolve_teamspace(teamspace="my-teamspace", org="my-org") is resolved
        mock_resolve.assert_called_once_with("my-teamspace", "my-org", None)
        mock_save.assert_called_once_with(resolved, overwrite=False)


def test_slug_with_org_conflict_raises_usage_error():
    """An 'owner/teamspace' slug combined with --org/--user is ambiguous and must fail loudly."""
    with pytest.raises(click.UsageError, match="already specifies the"):
        resolve_teamspace(teamspace="owner/my-teamspace", org="another-org")


def test_slug_with_user_conflict_raises_usage_error():
    with pytest.raises(click.UsageError, match="already specifies the"):
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
