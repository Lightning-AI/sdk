import click
from click.testing import CliRunner

from lightning_sdk.cli.legacy_redirects import mark_deprecated_command


def test_mark_deprecated_command_is_idempotent() -> None:
    @click.command("old")
    def old_command() -> None:
        click.echo("called")

    first_group = click.Group("first")
    first_group.add_command(mark_deprecated_command(old_command, "lightning new"))
    second_group = click.Group("second")
    second_group.add_command(mark_deprecated_command(old_command, "lightning new"))
    runner = CliRunner()

    for group in (first_group, second_group):
        help_result = runner.invoke(group, ["old", "--help"])
        assert help_result.exit_code == 0
        assert help_result.output.count("Deprecation warning:") == 1

        invoke_result = runner.invoke(group, ["old"])
        assert invoke_result.exit_code == 0
        assert invoke_result.output.count("Deprecation warning:") == 1
        assert "called" in invoke_result.output


def test_mark_deprecated_command_appends_detail() -> None:
    @click.command("old")
    def old_command() -> None:
        click.echo("called")

    group = click.Group("g")
    group.add_command(mark_deprecated_command(old_command, "lightning new", detail="Note the URL format differs."))
    runner = CliRunner()

    help_result = runner.invoke(group, ["old", "--help"])
    assert "Deprecation warning:" in help_result.output
    assert "Note the URL format differs." in help_result.output

    invoke_result = runner.invoke(group, ["old"])
    assert "Note the URL format differs." in invoke_result.output
    assert "called" in invoke_result.output
