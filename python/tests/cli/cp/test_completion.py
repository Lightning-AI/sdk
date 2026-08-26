from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import click
from click.shell_completion import get_completion_class
from click.testing import CliRunner

from lightning_sdk.cli.cp.completion import _accessible_teamspaces, complete_cp_path, complete_remote_path
from lightning_sdk.cli.entrypoint import main_cli
from lightning_sdk.cli.groups import cp
from lightning_sdk.cli.resource_completion import studios as _studios


def _values(items):
    return [item.value for item in items]


def _complete_argument(name, incomplete):
    parameter = next(parameter for parameter in cp.params if parameter.name == name)
    return parameter.shell_complete(click.Context(cp), incomplete)


def test_local_paths_use_native_shell_file_completion_for_both_arguments():
    for name in ("source", "destination"):
        items = _complete_argument(name, "local/pa")

        assert len(items) == 1
        assert items[0].value == "local/pa"
        assert items[0].type == "file"


@patch(
    "lightning_sdk.cli.cp.completion._accessible_teamspaces",
    return_value={"acme": {"research": "project-1", "vision": "project-2"}, "personal": {}},
)
@patch("lightning_sdk.cli.cp.completion.FilesystemApi")
def test_remote_completion_walks_owners_teamspaces_and_namespaces(filesystem_api, _accessible_teamspaces):
    ctx = click.Context(cp)
    parameter = next(parameter for parameter in cp.params if parameter.name == "source")

    assert _values(complete_cp_path(ctx, parameter, "lit://a")) == ["lit://acme/"]
    assert _values(complete_cp_path(ctx, parameter, "lit://acme/v")) == ["lit://acme/vision/"]

    # The namespace level comes from the drive's root listing, not a client-side list.
    filesystem_api.return_value.list_files.return_value = [
        {"path": "artifacts", "type": "tree"},
        {"path": "studios", "type": "tree"},
    ]
    assert _values(complete_cp_path(ctx, parameter, "lit://acme/research/s")) == ["lit://acme/research/studios/"]
    assert _values(complete_cp_path(ctx, parameter, "lit://acme/research/a")) == ["lit://acme/research/artifacts/"]
    filesystem_api.return_value.list_files.assert_called_with("project-1", "", recursive=False)


@patch(
    "lightning_sdk.cli.cp.completion._accessible_teamspaces",
    return_value={"acme": {"research": "project-1"}},
)
@patch("lightning_sdk.cli.cp.completion.FilesystemApi")
def test_remote_completion_lists_studios(filesystem_api, _accessible_teamspaces):
    filesystem_api.return_value.list_files.return_value = [
        {"path": "dev", "type": "tree"},
        {"path": "training", "type": "tree"},
    ]

    items = _complete_argument("source", "lit://acme/research/studios/d")

    assert _values(items) == ["lit://acme/research/studios/dev/"]
    filesystem_api.return_value.list_files.assert_called_once_with("project-1", "studios", recursive=False)


@patch(
    "lightning_sdk.cli.cp.completion._accessible_teamspaces",
    return_value={"acme": {"research": "project-1"}},
)
@patch("lightning_sdk.cli.cp.completion.FilesystemApi")
def test_remote_completion_lists_studio_files(filesystem_api, _accessible_teamspaces):
    filesystem_api.return_value.list_files.return_value = [
        {"path": "dataset.csv", "type": "blob"},
        {"path": "datasets", "type": "tree"},
        {"path": "notes.txt", "type": "blob"},
    ]

    items = _complete_argument("source", "lit://acme/research/studios/dev/da")

    assert _values(items) == [
        "lit://acme/research/studios/dev/dataset.csv",
        "lit://acme/research/studios/dev/datasets/",
    ]
    assert [item.type for item in items] == ["plain", "plain"]
    filesystem_api.return_value.list_files.assert_called_once_with("project-1", "studios/dev", recursive=False)


@patch(
    "lightning_sdk.cli.cp.completion._accessible_teamspaces",
    return_value={"acme": {"research": "project-1"}},
)
@patch("lightning_sdk.cli.cp.completion.FilesystemApi")
def test_remote_completion_lists_nested_teamspace_uploads(filesystem_api, _accessible_teamspaces):
    filesystem_api.return_value.list_files.return_value = [
        {"path": "model.ckpt", "type": "blob"},
        {"path": "models", "type": "tree"},
    ]

    items = _complete_argument("destination", "lit://acme/research/uploads/checkpoints/mo")

    assert _values(items) == [
        "lit://acme/research/uploads/checkpoints/model.ckpt",
        "lit://acme/research/uploads/checkpoints/models/",
    ]
    filesystem_api.return_value.list_files.assert_called_once_with("project-1", "uploads/checkpoints", recursive=False)


@patch("lightning_sdk.cli.cp.completion._accessible_teamspaces", side_effect=RuntimeError("offline"))
def test_remote_completion_silently_ignores_api_failures(_accessible_teamspaces):
    items = _complete_argument("source", "lit://")

    assert items == []


@patch("lightning_sdk.cli.cp.completion._accessible_teamspaces")
@patch("lightning_sdk.cli.resource_completion.Auth")
def test_remote_completion_does_not_start_login_without_credentials(auth, accessible_teamspaces):
    auth.return_value.api_key = None
    auth.return_value.auth_token = None
    auth.return_value.load.return_value = False

    items = _complete_argument("source", "lit://")

    assert items == []
    accessible_teamspaces.assert_not_called()


def test_accessible_teamspaces_are_grouped_by_owner():
    client = MagicMock()
    client.auth_service_get_user.return_value = SimpleNamespace(id="user-1", username="personal")
    client.organizations_service_list_organizations.return_value = SimpleNamespace(
        organizations=[SimpleNamespace(id="org-1", name="acme")]
    )
    client.projects_service_list_memberships.return_value = SimpleNamespace(
        memberships=[
            SimpleNamespace(owner_id="org-1", name="research", project_id="project-1"),
            SimpleNamespace(owner_id="user-1", name="scratch", project_id="project-2"),
        ]
    )

    with patch("lightning_sdk.cli.resource_completion.cached_lightning_client", return_value=client):
        assert _accessible_teamspaces() == {
            "acme": {"research": "project-1"},
            "personal": {"scratch": "project-2"},
        }

    client.projects_service_list_memberships.assert_called_once_with(filter_by_user_id=True)


def test_studio_listing_follows_pagination():
    first = SimpleNamespace(
        cloudspaces=[SimpleNamespace(name="dev", id="studio-1")],
        next_page_token="next",
    )
    second = SimpleNamespace(
        cloudspaces=[SimpleNamespace(name="training", id="studio-2")],
        next_page_token=None,
    )
    client = MagicMock()
    client.cloud_space_service_list_cloud_spaces.side_effect = [first, second]

    with patch("lightning_sdk.cli.resource_completion.cached_lightning_client", return_value=client):
        assert _studios("project-1") == {"dev": "studio-1", "training": "studio-2"}

    assert client.cloud_space_service_list_cloud_spaces.call_args_list[0].kwargs == {"project_id": "project-1"}
    assert client.cloud_space_service_list_cloud_spaces.call_args_list[1].kwargs == {
        "project_id": "project-1",
        "page_token": "next",
    }


def test_click_shell_protocol_returns_native_local_completion():
    result = CliRunner().invoke(
        main_cli,
        prog_name="lightning",
        env={
            "_LIGHTNING_COMPLETE": "bash_complete",
            "COMP_WORDS": "lightning cp local/pa",
            "COMP_CWORD": "2",
        },
    )

    assert result.exit_code == 0
    assert result.output == "file,local/pa\n"


def test_generated_shell_scripts_preserve_remote_directory_completion():
    bash_completion = get_completion_class("bash")
    zsh_completion = get_completion_class("zsh")

    assert bash_completion is not None
    assert zsh_completion is not None
    assert "compopt -o nospace" in bash_completion.source_template
    assert "compadd -S ''" in zsh_completion.source_template


def test_remote_only_completion_never_offers_local_files():
    from lightning_sdk.cli.ls import ls as ls_command
    from lightning_sdk.cli.rm import rm as rm_command

    for command in (ls_command, rm_command):
        parameter = next(parameter for parameter in command.params if parameter.name == "path")
        assert parameter._custom_shell_complete is complete_remote_path

    ctx = click.Context(cp)
    parameter = next(parameter for parameter in cp.params if parameter.name == "source")

    # A local path gets no completions rather than the shell's file fallback...
    assert complete_remote_path(ctx, parameter, "local/pa") == []
    # ...and an empty or partial prefix steers toward lit://.
    assert _values(complete_remote_path(ctx, parameter, "")) == ["lit://"]
    assert _values(complete_remote_path(ctx, parameter, "li")) == ["lit://"]


@patch(
    "lightning_sdk.cli.cp.completion._accessible_teamspaces",
    return_value={"acme": {"research": "project-1"}},
)
def test_remote_only_completion_walks_lit_paths(_accessible_teamspaces):
    ctx = click.Context(cp)
    parameter = next(parameter for parameter in cp.params if parameter.name == "source")

    assert _values(complete_remote_path(ctx, parameter, "lit://a")) == ["lit://acme/"]


@patch("lightning_sdk.utils.resolve._resolve_teamspace")
@patch("lightning_sdk.cli.cp.completion.FilesystemApi")
def test_remote_completion_relative_form_uses_current_teamspace(filesystem_api, resolve_teamspace):
    resolve_teamspace.return_value = SimpleNamespace(id="project-1")
    filesystem_api.return_value.list_files.return_value = [
        {"path": "artifacts", "type": "tree"},
        {"path": "uploads", "type": "tree"},
    ]

    items = _complete_argument("source", "lit:///u")

    assert _values(items) == ["lit:///uploads/"]
    filesystem_api.return_value.list_files.assert_called_once_with("project-1", "", recursive=False)


@patch("lightning_sdk.utils.resolve._resolve_teamspace", return_value=None)
def test_remote_completion_relative_form_without_current_teamspace_is_empty(_resolve_teamspace):
    assert _complete_argument("source", "lit:///u") == []
