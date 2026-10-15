"""LLM CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register llm commands with the given group."""
    from lightning_sdk.cli.llm.list import list_llms

    group.add_command(list_llms, name="list")
