import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lightning_sdk.cli.auth.role import role
from lightning_sdk.cli.auth.roles import roles
from tests.cli.help import assert_help_contains, mock_command_logging


def _teamspace() -> SimpleNamespace:
    return SimpleNamespace(id="proj-1", name="research", owner=SimpleNamespace(name="acme"))


def _rule(effect: str, actions: list, resources: list, condition: object = None) -> SimpleNamespace:
    return SimpleNamespace(effect=effect, actions=actions, resources=resources, condition=condition)


@mock_command_logging
def test_auth_roles_help() -> None:
    assert_help_contains(
        "lightning auth roles --help",
        "Usage: lightning auth roles",
        "List the roles in a teamspace",
        "--teamspace",
        "--json",
    )


@mock_command_logging
def test_auth_role_help() -> None:
    assert_help_contains(
        "lightning auth role --help",
        "Usage: lightning auth role",
        "Describe what a role is allowed to do.",
    )


@mock_command_logging
def test_roles_marks_the_ones_you_hold() -> None:
    api = MagicMock()
    api.my_role_ids.return_value = {"r-1"}
    api.list_roles.return_value = [
        SimpleNamespace(id="r-1", name="Admin", description="Full access", rules=[1, 2, 3]),
        SimpleNamespace(id="r-2", name="Member", description="", rules=[]),
    ]

    with (
        patch("lightning_sdk.cli.auth.roles.TeamspacesMenu") as menu_cls,
        patch("lightning_sdk.cli.auth.roles.AuthApi", return_value=api),
        patch("lightning_sdk.cli.auth.roles._get_authed_user", return_value=SimpleNamespace(id="u-1")),
    ):
        menu_cls.return_value.return_value = _teamspace()
        result = CliRunner().invoke(roles, ["--teamspace", "acme/research"])

    assert result.exit_code == 0, result.output
    assert "Admin" in result.output
    assert "Member" in result.output
    assert "✓" in result.output  # the held role is marked
    api.my_role_ids.assert_called_once_with("proj-1", "u-1")


@mock_command_logging
def test_roles_json() -> None:
    api = MagicMock()
    api.my_role_ids.return_value = {"r-1"}
    api.list_roles.return_value = [
        SimpleNamespace(id="r-1", name="Admin", description="Full access", rules=[1, 2]),
    ]

    with (
        patch("lightning_sdk.cli.auth.roles.TeamspacesMenu") as menu_cls,
        patch("lightning_sdk.cli.auth.roles.AuthApi", return_value=api),
        patch("lightning_sdk.cli.auth.roles._get_authed_user", return_value=SimpleNamespace(id="u-1")),
    ):
        menu_cls.return_value.return_value = _teamspace()
        result = CliRunner().invoke(roles, ["--teamspace", "acme/research", "--json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data == [{"id": "r-1", "name": "Admin", "description": "Full access", "permissions": 2, "yours": True}]


@mock_command_logging
def test_role_uses_external_facing_resource_names() -> None:
    api = MagicMock()
    api.get_role.return_value = SimpleNamespace(
        id="r-1",
        name="Member",
        description="",
        rules=[_rule("allow", ["get", "create"], ["cloudSpace", "project"])],
    )

    with (
        patch("lightning_sdk.cli.auth.role.TeamspacesMenu") as menu_cls,
        patch("lightning_sdk.cli.auth.role.AuthApi", return_value=api),
    ):
        menu_cls.return_value.return_value = _teamspace()
        result = CliRunner().invoke(role, ["r-1", "--teamspace", "acme/research"])

    assert result.exit_code == 0, result.output
    # Internal enum names must not leak; external labels are shown instead.
    assert "Studios" in result.output
    assert "Teamspaces" in result.output
    assert "cloudSpace" not in result.output
    assert "project" not in result.output
    api.get_role.assert_called_once_with("proj-1", "r-1")


@mock_command_logging
def test_role_json_uses_external_names_and_conditions() -> None:
    condition = SimpleNamespace(resource_owner=True, resource_id=None, cloudspace_id=None, project_id=None)
    api = MagicMock()
    api.get_role.return_value = SimpleNamespace(
        id="r-1",
        name="Member",
        description="Standard member",
        rules=[_rule("allow", ["delete"], ["cloudSpace"], condition)],
    )

    with (
        patch("lightning_sdk.cli.auth.role.TeamspacesMenu") as menu_cls,
        patch("lightning_sdk.cli.auth.role.AuthApi", return_value=api),
    ):
        menu_cls.return_value.return_value = _teamspace()
        result = CliRunner().invoke(role, ["r-1", "--teamspace", "acme/research", "--json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["name"] == "Member"
    assert data["permissions"] == [
        {"resource": "Studios", "actions": "Delete", "effect": "Allow", "condition": "own resources only"}
    ]


@mock_command_logging
def test_role_hides_unspecified_sentinels() -> None:
    api = MagicMock()
    api.get_role.return_value = SimpleNamespace(
        id="r-1",
        name="Admin",
        description="",
        rules=[
            _rule("allow", ["get", "unspecifiedAction"], ["cloudSpace", "unspecifiedResource"]),
            _rule("deny", ["unspecifiedAction"], ["project"]),  # only a hidden action -> whole row dropped
        ],
    )

    with (
        patch("lightning_sdk.cli.auth.role.TeamspacesMenu") as menu_cls,
        patch("lightning_sdk.cli.auth.role.AuthApi", return_value=api),
    ):
        menu_cls.return_value.return_value = _teamspace()
        result = CliRunner().invoke(role, ["r-1", "--teamspace", "acme/research", "--json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    # unspecified action/resource dropped; the all-unspecified deny rule produces no rows.
    assert data["permissions"] == [{"resource": "Studios", "actions": "Get", "effect": "Allow", "condition": None}]
    assert "Unspecified" not in result.output
