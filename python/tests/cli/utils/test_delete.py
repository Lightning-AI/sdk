import json
from typing import ClassVar, Optional

import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli.utils.delete import register_delete_command


class FakeResource:
    instances: ClassVar[list["FakeResource"]] = []

    def __init__(self, name: str, teamspace: Optional[str] = None, marker: str = "") -> None:
        self.name = name
        self.teamspace = teamspace
        self.marker = marker
        self.deleted = False
        self.__class__.instances.append(self)

    def delete(self) -> None:
        self.deleted = True


def _group() -> click.Group:
    group = click.Group()
    register_delete_command(
        group,
        FakeResource,
        label="Widget",
        help="Delete a widget.",
        resource_kwargs={"marker": "registered"},
    )
    return group


def test_delete_prompts_with_default_yes_and_prints_success() -> None:
    FakeResource.instances.clear()
    result = CliRunner().invoke(_group(), ["delete", "demo"], input="\n")

    assert result.exit_code == 0
    assert result.output == "Are you sure you want to delete? [Y/n]: \nWidget deleted\n"
    resource = FakeResource.instances[-1]
    assert (resource.name, resource.teamspace, resource.marker, resource.deleted) == (
        "demo",
        None,
        "registered",
        True,
    )


def test_delete_no_aborts_without_deleting() -> None:
    FakeResource.instances.clear()
    result = CliRunner().invoke(_group(), ["delete", "demo"], input="n\n")

    assert result.exit_code == 1
    assert "Aborted!" in result.output
    assert FakeResource.instances[-1].deleted is False


def test_delete_yes_flag_skips_prompt() -> None:
    FakeResource.instances.clear()
    result = CliRunner().invoke(_group(), ["delete", "demo", "-y"])

    assert result.exit_code == 0
    assert result.output == "Widget deleted\n"
    assert FakeResource.instances[-1].deleted is True


def test_delete_json_preserves_machine_readable_output() -> None:
    FakeResource.instances.clear()
    result = CliRunner().invoke(_group(), ["delete", "demo", "-y", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"name": "demo", "deleted": True}
    assert FakeResource.instances[-1].deleted is True


def test_delete_uses_registration_local_resolver() -> None:
    calls = []

    def resolve_delete(identifier: str, context: Optional[str]):
        calls.append((identifier, context))
        return lambda: calls.append("deleted")

    group = click.Group()
    register_delete_command(
        group,
        label="API key",
        help="Delete an API key.",
        identifier="key_id",
        context_option="org",
        resolve_delete=resolve_delete,
    )

    result = CliRunner().invoke(group, ["delete", "key-123", "--org", "acme", "-y"])

    assert result.exit_code == 0
    assert result.output == "API key deleted\n"
    assert calls == [("key-123", "acme"), "deleted"]
