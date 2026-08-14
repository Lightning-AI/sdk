from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import click
from click.shell_completion import get_completion_class
from click.testing import CliRunner

from lightning_sdk.cli.cp.completion import _accessible_teamspaces, _studios, complete_cp_path
from lightning_sdk.cli.entrypoint import main_cli
from lightning_sdk.cli.groups import cp


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
def test_remote_completion_walks_owners_teamspaces_and_resource_types(_accessible_teamspaces):
    ctx = click.Context(cp)
    parameter = next(parameter for parameter in cp.params if parameter.name == "source")

    assert _values(complete_cp_path(ctx, parameter, "lit://a")) == ["lit://acme/"]
    assert _values(complete_cp_path(ctx, parameter, "lit://acme/v")) == ["lit://acme/vision/"]
    assert _values(complete_cp_path(ctx, parameter, "lit://acme/research/s")) == ["lit://acme/research/studios/"]


@patch(
    "lightning_sdk.cli.cp.completion._accessible_teamspaces",
    return_value={"acme": {"research": "project-1"}},
)
@patch(
    "lightning_sdk.cli.cp.completion._studios",
    return_value={"dev": "studio-1", "training": "studio-2"},
)
def test_remote_completion_lists_studios(_studios, _accessible_teamspaces):
    items = _complete_argument("source", "lit://acme/research/studios/d")

    assert _values(items) == ["lit://acme/research/studios/dev/"]


@patch(
    "lightning_sdk.cli.cp.completion._accessible_teamspaces",
    return_value={"acme": {"research": "project-1"}},
)
@patch(
    "lightning_sdk.cli.cp.completion._studios",
    return_value={"dev": "studio-1"},
)
@patch("lightning_sdk.cli.cp.completion.StudioApi")
def test_remote_completion_lists_studio_files(studio_api, _studios, _accessible_teamspaces):
    studio_api.return_value.get_tree.return_value = {
        "tree": [
            {"path": "dataset.csv", "type": "blob"},
            {"path": "datasets", "type": "tree"},
            {"path": "notes.txt", "type": "blob"},
        ]
    }

    items = _complete_argument("source", "lit://acme/research/studios/dev/da")

    assert _values(items) == [
        "lit://acme/research/studios/dev/dataset.csv",
        "lit://acme/research/studios/dev/datasets/",
    ]
    assert [item.type for item in items] == ["plain", "plain"]
    studio_api.return_value.get_tree.assert_called_once_with("studio-1", "project-1", path="")


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
    filesystem_api.return_value.list_files.assert_called_once_with("project-1", "Uploads/checkpoints", recursive=False)


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
    client.auth_service_get_user.return_value.get.return_value = SimpleNamespace(id="user-1", username="personal")
    client.organizations_service_list_organizations.return_value.get.return_value = SimpleNamespace(
        organizations=[SimpleNamespace(id="org-1", name="acme")]
    )
    client.projects_service_list_memberships.return_value.get.return_value = SimpleNamespace(
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

    client.auth_service_get_user.assert_called_once_with(async_req=True)
    client.organizations_service_list_organizations.assert_called_once_with(async_req=True)
    client.projects_service_list_memberships.assert_called_once_with(filter_by_user_id=True, async_req=True)


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
