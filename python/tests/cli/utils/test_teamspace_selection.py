from unittest.mock import MagicMock

import pytest

from lightning_sdk.cli.utils import teamspace_selection
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.organization import Organization


def test_explicit_owner_teamspace_is_used_directly(monkeypatch):
    """When 'owner/teamspace' resolves, it is returned without touching interactive menus."""
    resolved = MagicMock()
    monkeypatch.setattr(teamspace_selection, "resolve_teamspace_owner_name_format", MagicMock(return_value=resolved))
    # If any of these are reached we are no longer non-interactive.
    owner_menu = MagicMock(side_effect=AssertionError("OwnerMenu should not be used"))
    monkeypatch.setattr("lightning_sdk.cli.utils.owner_selection.OwnerMenu", owner_menu)

    assert TeamspacesMenu()(teamspace="lightning-ai/agents-teamspace") is resolved


def test_explicit_owner_teamspace_raises_instead_of_prompting(monkeypatch):
    """An unresolved 'owner/teamspace' must raise a clear error, not fall back to a prompt.

    The interactive fallback resolves the authenticated user, which is unavailable for
    org/teamspace-scoped API keys - so falling through would break those keys entirely.
    """
    monkeypatch.setattr(teamspace_selection, "resolve_teamspace_owner_name_format", MagicMock(return_value=None))
    owner_menu = MagicMock(side_effect=AssertionError("OwnerMenu should not be used"))
    monkeypatch.setattr("lightning_sdk.cli.utils.owner_selection.OwnerMenu", owner_menu)
    monkeypatch.setattr(
        teamspace_selection,
        "_get_authed_user",
        MagicMock(side_effect=AssertionError("authed user should not be resolved")),
    )

    with pytest.raises(ValueError, match="Could not resolve teamspace 'lightning-ai/does-not-exist'"):
        TeamspacesMenu()(teamspace="lightning-ai/does-not-exist")


def test_bare_teamspace_name_still_falls_back(monkeypatch):
    """A teamspace without an explicit owner keeps the existing (possibly interactive) flow."""
    monkeypatch.setattr(teamspace_selection, "resolve_teamspace_owner_name_format", MagicMock(return_value=None))
    # The owner gets resolved (here via the menu) and resolution proceeds with org scope.
    owner = MagicMock(spec=Organization)
    monkeypatch.setattr(
        "lightning_sdk.cli.utils.owner_selection.OwnerMenu", MagicMock(return_value=MagicMock(return_value=owner))
    )
    monkeypatch.setattr(teamspace_selection, "_resolve_teamspace", MagicMock(return_value="resolved-teamspace"))

    # No '/' in the name -> must not hit the explicit-owner guard, so resolution proceeds.
    assert TeamspacesMenu()(teamspace="just-a-name") == "resolved-teamspace"
