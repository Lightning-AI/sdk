from unittest.mock import patch

import click
from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli
from lightning_sdk.cli.resource_completion import complete_studio, complete_teamspace


def _values(items):
    return [item.value for item in items]


@patch("lightning_sdk.cli.resource_completion.has_credentials", return_value=True)
@patch(
    "lightning_sdk.cli.resource_completion.accessible_teamspaces",
    return_value={"acme": {"research": "project-1", "vision": "project-2"}, "personal": {"scratch": "project-3"}},
)
def test_teamspace_completion_matches_owner_or_teamspace_prefix(accessible_teamspaces, has_credentials):
    ctx = click.Context(main_cli)
    parameter = click.Option(["--teamspace"])

    assert _values(complete_teamspace(ctx, parameter, "ac")) == ["acme/research", "acme/vision"]
    assert _values(complete_teamspace(ctx, parameter, "res")) == ["acme/research"]


@patch("lightning_sdk.cli.resource_completion.has_credentials", return_value=True)
@patch(
    "lightning_sdk.cli.resource_completion.accessible_teamspaces",
    return_value={"acme": {"research": "project-1"}, "personal": {"research": "project-2"}},
)
@patch(
    "lightning_sdk.cli.resource_completion.studios",
    side_effect=lambda teamspace_id: {
        "project-1": {"dev": "studio-1", "training": "studio-2"},
        "project-2": {"personal-dev": "studio-3"},
    }[teamspace_id],
)
def test_studio_completion_uses_selected_teamspace(studios, accessible_teamspaces, has_credentials):
    ctx = click.Context(main_cli)
    ctx.params = {"teamspace": "acme/research"}
    parameter = click.Option(["--name"])

    assert _values(complete_studio(ctx, parameter, "d")) == ["dev"]
    studios.assert_called_once_with("project-1")


@patch("lightning_sdk.cli.resource_completion.has_credentials", return_value=False)
@patch("lightning_sdk.cli.resource_completion.accessible_teamspaces")
def test_resource_completion_does_not_resolve_without_credentials(accessible_teamspaces, has_credentials):
    ctx = click.Context(main_cli)
    parameter = click.Option(["--teamspace"])

    assert complete_teamspace(ctx, parameter, "") == []
    accessible_teamspaces.assert_not_called()


def test_resource_callbacks_are_wired_only_to_resource_parameters():
    studio_stop = main_cli.commands["studio"].commands["stop"]
    teamspace = next(parameter for parameter in studio_stop.params if parameter.name == "teamspace")
    studio_name = next(parameter for parameter in studio_stop.params if parameter.name == "name")
    create_name = next(
        parameter for parameter in main_cli.commands["studio"].commands["create"].params if parameter.name == "name"
    )
    job_studio = next(
        parameter for parameter in main_cli.commands["job"].commands["run"].params if parameter.name == "studio"
    )

    assert teamspace._custom_shell_complete is complete_teamspace
    assert studio_name._custom_shell_complete is complete_studio
    assert job_studio._custom_shell_complete is complete_studio
    assert create_name._custom_shell_complete is None


@patch("lightning_sdk.cli.resource_completion.has_credentials", return_value=True)
@patch(
    "lightning_sdk.cli.resource_completion.accessible_teamspaces",
    return_value={"acme": {"research": "project-1"}},
)
def test_click_shell_protocol_completes_teamspace_option(accessible_teamspaces, has_credentials):
    result = CliRunner().invoke(
        main_cli,
        prog_name="lightning",
        env={
            "_LIGHTNING_COMPLETE": "bash_complete",
            "COMP_WORDS": "lightning studio stop --teamspace res",
            "COMP_CWORD": "4",
        },
    )

    assert result.exit_code == 0
    assert result.output == "plain,acme/research\n"


@patch("lightning_sdk.cli.resource_completion.has_credentials", return_value=True)
@patch(
    "lightning_sdk.cli.resource_completion.accessible_teamspaces",
    return_value={"acme": {"research": "project-1"}},
)
@patch("lightning_sdk.cli.resource_completion.studios", return_value={"dev": "studio-1", "training": "studio-2"})
def test_click_shell_protocol_completes_studio_in_selected_teamspace(studios, accessible_teamspaces, has_credentials):
    result = CliRunner().invoke(
        main_cli,
        prog_name="lightning",
        env={
            "_LIGHTNING_COMPLETE": "bash_complete",
            "COMP_WORDS": "lightning studio stop --teamspace acme/research --name d",
            "COMP_CWORD": "6",
        },
    )

    assert result.exit_code == 0
    assert result.output == "plain,dev\n"
    studios.assert_called_once_with("project-1")
