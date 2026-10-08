import json
from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli
from lightning_sdk.lightning_cloud.openapi import V1Membership, V1Organization, V1SearchUser
from tests.cli.help import assert_help_contains, mock_command_logging


def _membership(name: str, owner_id: str, owner_type: str, display_name: str = "") -> V1Membership:
    return V1Membership(
        name=name,
        owner_id=owner_id,
        owner_type=owner_type,
        display_name=display_name,
        project_id=f"project-{owner_id}-{name}",
    )


@pytest.fixture()
def client() -> Iterator[MagicMock]:
    """Fake generated client with two org teamspaces, the user's own one, and one shared by another user."""
    client = MagicMock()
    client.projects_service_list_memberships.return_value.memberships = [
        _membership("general", "org-ai", "organization", "General"),
        _membership("default-project", "user-me", "user", "Default"),
        _membership("skills-efficacy", "org-eng", "organization", "Skills Efficacy"),
        _membership("shared", "user-ada", "user"),
    ]
    client.organizations_service_list_organizations.return_value.organizations = [
        V1Organization(id="org-ai", name="lightning-ai"),
        V1Organization(id="org-eng", name="lightningai-engineering"),
    ]
    users = {
        "user-me": V1SearchUser(id="user-me", username="sjoshi"),
        "user-ada": V1SearchUser(id="user-ada", username="ada"),
    }
    client.user_service_search_users.side_effect = lambda query: MagicMock(users=[users[query]])

    with patch("lightning_sdk.api.user_api.cached_lightning_client", return_value=client), patch(
        "lightning_sdk.api.org_api.cached_lightning_client", return_value=client
    ), patch("lightning_sdk.cli.teamspace.list._configured_teamspace", return_value=None):
        yield client


def _list(*args: str) -> list:
    result = CliRunner().invoke(main_cli, ["teamspace", "list", "--json", *args])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


@mock_command_logging
def test_teamspace_list_help() -> None:
    assert_help_contains(
        "lightning teamspace list --help",
        "Usage: lightning teamspace list",
        "List the teamspaces you are a member of.",
    )


@mock_command_logging
def test_teamspace_list_resolves_owner_names_for_org_and_user_teamspaces(client: MagicMock) -> None:
    rows = _list()

    assert [(row["teamspace"], row["owner_type"]) for row in rows] == [
        ("ada/shared", "user"),
        ("lightning-ai/general", "organization"),
        ("lightningai-engineering/skills-efficacy", "organization"),
        ("sjoshi/default-project", "user"),
    ]
    assert rows[1] == {
        "teamspace": "lightning-ai/general",
        "owner": "lightning-ai",
        "name": "general",
        "owner_type": "organization",
        "display_name": "General",
        "current": False,
    }
    # Orgs come from one listing call; per-org lookups are not needed.
    client.organizations_service_get_organization.assert_not_called()


@mock_command_logging
def test_teamspace_list_looks_up_orgs_missing_from_the_org_listing(client: MagicMock) -> None:
    client.projects_service_list_memberships.return_value.memberships.append(
        _membership("guest", "org-other", "organization")
    )
    client.organizations_service_get_organization.return_value = V1Organization(id="org-other", name="partner")

    assert "partner/guest" in [row["teamspace"] for row in _list()]
    client.organizations_service_get_organization.assert_called_once_with(id="org-other")


@mock_command_logging
def test_teamspace_list_table_shows_slugs_and_owner_types(client: MagicMock) -> None:
    result = CliRunner().invoke(main_cli, ["teamspace", "list"], env={"COLUMNS": "200"})

    assert result.exit_code == 0, result.output
    lines = {line.split("│")[1].strip(): line for line in result.output.splitlines() if line.count("│") > 2}
    assert "lightning-ai/general" in lines
    assert "organization" in lines["lightning-ai/general"]
    assert "user" in lines["sjoshi/default-project"]


@mock_command_logging
@pytest.mark.parametrize(
    ("configured", "current"),
    [
        ("lightningai-engineering/skills-efficacy", ["lightningai-engineering/skills-efficacy"]),
        ("general", ["lightning-ai/general"]),
        ("no-such-teamspace", []),
    ],
)
def test_teamspace_list_marks_the_configured_teamspace(client: MagicMock, configured: str, current: list) -> None:
    with patch("lightning_sdk.cli.teamspace.list._configured_teamspace", return_value=configured):
        rows = _list()

    assert [row["teamspace"] for row in rows if row["current"]] == current


@mock_command_logging
def test_teamspace_list_bare_configured_name_shared_by_two_owners_marks_none(client: MagicMock) -> None:
    client.projects_service_list_memberships.return_value.memberships.append(
        _membership("general", "org-eng", "organization")
    )
    with patch("lightning_sdk.cli.teamspace.list._configured_teamspace", return_value="general"):
        rows = _list()

    assert not any(row["current"] for row in rows)


@mock_command_logging
def test_teamspace_list_filters_on_a_real_value_for_every_key(client: MagicMock) -> None:
    """Every key acts on the field it names: a matching pattern keeps one row, a wrong one keeps none."""
    patterns = {
        "teamspace": "lightningai-engineering/skills-efficacy",
        "owner": "lightningai-engineering",
        "name": "skills-efficacy",
        "owner-type": "organization",
        "display-name": "Skills Efficacy",
    }
    expected = {
        "teamspace": ["lightningai-engineering/skills-efficacy"],
        "owner": ["lightningai-engineering/skills-efficacy"],
        "name": ["lightningai-engineering/skills-efficacy"],
        "owner-type": ["lightning-ai/general", "lightningai-engineering/skills-efficacy"],
        "display-name": ["lightningai-engineering/skills-efficacy"],
    }

    for key, pattern in patterns.items():
        assert [row["teamspace"] for row in _list("--filter", f"{key}={pattern}")] == expected[key], key
        assert _list("--filter", f"{key}=nothing-looks-like-this") == [], key


@mock_command_logging
def test_teamspace_list_filters_combine_and_glob(client: MagicMock) -> None:
    rows = _list("--filter", "owner-type=user,name=default-*")

    assert [row["teamspace"] for row in rows] == ["sjoshi/default-project"]


@mock_command_logging
def test_teamspace_list_rejects_unknown_filter_key(client: MagicMock) -> None:
    result = CliRunner().invoke(main_cli, ["teamspace", "list", "--filter", "project-id=x"])

    assert result.exit_code != 0
    assert "unknown key 'project-id'" in result.output


@mock_command_logging
@pytest.mark.parametrize(
    ("sort_by", "expected"),
    [
        (
            "owner-type",
            [
                "lightning-ai/general",
                "lightningai-engineering/skills-efficacy",
                "ada/shared",
                "sjoshi/default-project",
            ],
        ),
        (
            "name",
            [
                "sjoshi/default-project",
                "lightning-ai/general",
                "ada/shared",
                "lightningai-engineering/skills-efficacy",
            ],
        ),
        (
            "display-name",
            [
                "ada/shared",
                "sjoshi/default-project",
                "lightning-ai/general",
                "lightningai-engineering/skills-efficacy",
            ],
        ),
    ],
)
def test_teamspace_list_sorts_by_row_fields(client: MagicMock, sort_by: str, expected: list) -> None:
    assert [row["teamspace"] for row in _list("--sort-by", sort_by)] == expected
