"""API CLI commands."""

import re

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningGroup

_RAW_API_COMMAND_NAME = "__request"
_RELATIVE_API_PATH_RE = re.compile(r"^v\d+(?:/|$)")
_OPTIONS_WITH_VALUES = {
    "--cache",
    "--field",
    "--header",
    "--hostname",
    "--input",
    "--jq",
    "--method",
    "--raw-field",
}
_SHORT_OPTIONS_WITH_VALUES = {"-F", "-H", "-q", "-X", "-f"}


def _looks_like_api_path(value: str) -> bool:
    return value.startswith(("/", "http://", "https://")) or bool(_RELATIVE_API_PATH_RE.match(value))


def _request_path_arg(args: list[str]) -> str | None:
    skip_next = False
    for index, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg == "--":
            return next((value for value in args[index + 1 :] if value != ""), None)
        if arg.startswith("--"):
            option = arg.split("=", 1)[0]
            if option in _OPTIONS_WITH_VALUES and "=" not in arg:
                skip_next = True
            continue
        if arg.startswith("-") and arg != "-":
            option = arg[:2]
            if option in _SHORT_OPTIONS_WITH_VALUES and len(arg) == 2:
                skip_next = True
            continue
        return arg
    return None


class APIGroup(LightningGroup):
    """API command group with a raw HTTP request fallback."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if args and self._should_use_raw_request(ctx, args):
            args = [_RAW_API_COMMAND_NAME, *args]
        return super().parse_args(ctx, args)

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            path_arg = _request_path_arg(args)
            if path_arg and _looks_like_api_path(path_arg):
                return _RAW_API_COMMAND_NAME, self.commands[_RAW_API_COMMAND_NAME], args
            raise

    def _should_use_raw_request(self, ctx: click.Context, args: list[str]) -> bool:
        if args[0] in self.commands or args[0] in self.get_help_option_names(ctx):
            return False
        path_arg = _request_path_arg(args)
        return bool(path_arg and _looks_like_api_path(path_arg))


def register_commands(group: click.Group) -> None:
    """Register API commands with the given group."""
    from lightning_sdk.cli.api.deploy import deploy_api
    from lightning_sdk.cli.api.dockerize import dockerize_api
    from lightning_sdk.cli.api.request import api_request

    group.add_command(deploy_api, name="deploy")
    group.add_command(dockerize_api, name="dockerize")
    group.add_command(api_request, name=_RAW_API_COMMAND_NAME)
