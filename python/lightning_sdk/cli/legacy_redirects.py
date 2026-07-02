"""Hidden CLI aliases for deprecated verb-first commands and plural nouns."""

from __future__ import annotations

from typing import Mapping

import click

from lightning_sdk.cli.utils.logging import LightningGroup


def _format_redirect_message(old_command: str, replacement: str) -> str:
    return f"Use `{replacement}` instead of `{old_command}`."


def _format_deprecation_warning(old_command: str, replacement: str) -> str:
    return f"Deprecation warning: {_format_redirect_message(old_command, replacement)}"


def _echo_deprecation_warning(old_command: str, replacement: str) -> None:
    click.secho(_format_deprecation_warning(old_command, replacement), fg="yellow", err=True)


class DeprecatedForwardCommand(click.Command):
    """A hidden deprecated command alias that forwards to the replacement command."""

    def __init__(self, *args: object, replacement: str, target_command: click.Command, **kwargs: object) -> None:
        kwargs.setdefault("hidden", True)
        kwargs.setdefault("help", target_command.help)
        kwargs.setdefault("short_help", target_command.short_help)
        kwargs.setdefault("epilog", target_command.epilog)
        kwargs.setdefault("params", target_command.params)
        kwargs.setdefault("callback", target_command.callback)
        kwargs.setdefault("context_settings", target_command.context_settings)
        super().__init__(*args, **kwargs)
        self.replacement = replacement
        self.target_command = target_command

    def get_help(self, ctx: click.Context) -> str:
        return f"{_format_deprecation_warning(ctx.command_path, self.replacement)}\n\n{super().get_help(ctx)}"

    def invoke(self, ctx: click.Context) -> object:
        _echo_deprecation_warning(ctx.command_path, self.replacement)
        return super().invoke(ctx)


class LegacyForwardGroup(click.Group):
    """A hidden deprecated group that forwards verb-first commands to noun-first commands."""

    def __init__(
        self,
        *args: object,
        replacements: Mapping[str, tuple[str, click.Command]],
        **kwargs: object,
    ) -> None:
        kwargs.setdefault("hidden", True)
        kwargs.setdefault("add_help_option", False)
        super().__init__(*args, **kwargs)
        self.replacements = dict(replacements)

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if not args or args[0] in {"--help", "-h"}:
            replacements = "\n".join(
                f"  {old} -> {new}" for old, (new, _) in sorted(self.replacements.items(), key=lambda item: item[0])
            )
            raise click.ClickException(f"`{ctx.command_path}` has moved to noun-first commands:\n{replacements}")
        return super().parse_args(ctx, args)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        replacement = self.replacements.get(cmd_name)
        if replacement is None:
            return None

        target_path, target_command = replacement
        return DeprecatedForwardCommand(name=cmd_name, replacement=target_path, target_command=target_command)

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(self.replacements)


def build_legacy_forward_group(name: str, replacements: Mapping[str, tuple[str, click.Command]]) -> LegacyForwardGroup:
    return LegacyForwardGroup(name=name, replacements=replacements)


def build_legacy_forward_command(
    name: str, replacement: str, target_command: click.Command
) -> DeprecatedForwardCommand:
    return DeprecatedForwardCommand(name=name, replacement=replacement, target_command=target_command)


class HiddenAliasGroup(LightningGroup):
    """A hidden plural alias that forwards to another noun-first group."""

    def __init__(self, *args: object, target_group: click.Group, **kwargs: object) -> None:
        kwargs.setdefault("hidden", True)
        kwargs.setdefault("help", target_group.help)
        super().__init__(*args, **kwargs)
        self.target_group = target_group

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        return self.target_group.get_command(ctx, cmd_name)

    def list_commands(self, ctx: click.Context) -> list[str]:
        return self.target_group.list_commands(ctx)


def build_hidden_alias_group(name: str, target_group: click.Group) -> HiddenAliasGroup:
    return HiddenAliasGroup(name=name, target_group=target_group)
