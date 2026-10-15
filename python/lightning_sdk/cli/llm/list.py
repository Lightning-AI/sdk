"""LLM list command."""

import re
from dataclasses import asdict
from fnmatch import fnmatchcase
from typing import Any, Dict, List, Optional, Sequence, Tuple

import rich_click as click
from rich.console import Console
from rich.table import Table

from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.llm import LLM

# Each key `--sort-by` and `--filter` accept, mapped to the HostedModel field it reads.
# Both options derive their keys from this one mapping, so they stay in parity.
_KEY_FIELDS = {
    "name": "name",
    "provider": "provider",
    "status": "status",
    "context": "context_length",
    "prompt-price": "prompt_usd_per_1m_tokens",
    "completion-price": "completion_usd_per_1m_tokens",
}
LIST_KEYS = tuple(_KEY_FIELDS)

# Only a comma that introduces the next KEY= pair separates filters.
_FILTER_SEPARATOR = re.compile(r",(?=\s*(?:" + "|".join(re.escape(key) for key in LIST_KEYS) + r")\s*=)")


@click.command("list", cls=LightningCommand)
@click.option(
    "--sort-by",
    "--sort_by",
    default=None,
    type=click.Choice(list(LIST_KEYS), case_sensitive=False),
    help="the attribute to sort the models by. Numbers sort ascending, with unknown values last.",
)
@click.option(
    "--filter",
    "filters",
    default=(),
    multiple=True,
    metavar="KEY=PATTERN",
    help=(
        "Only list models whose KEY matches PATTERN, a case-insensitive glob compared against the value as shown "
        "in the table. Can be a comma-separated list or passed multiple times, and every filter has to match. "
        f"KEY is one of: {', '.join(LIST_KEYS)}."
    ),
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_llms(sort_by: Optional[str] = None, filters: Sequence[str] = (), as_json: bool = False) -> None:
    """List hosted LLMs available through the Lightning model gateway.

    NAME is the provider/model identifier to call, e.g. with `LLM("openai/gpt-5")`.
    Prices are in USD per 1M tokens.

    Example:
        lightning llm list
        lightning llm list --filter 'provider=lightning-ai'
        lightning llm list --sort-by prompt-price --json

    """
    wanted_filters = _resolve_filters(filters)
    rows = [asdict(model) for model in LLM.list_models()]
    rows = [row for row in rows if _matches_filters(row, wanted_filters)]
    rows.sort(key=_sort_key(sort_by or "name"))

    if as_json:
        echo_json(rows)
        return

    table = Table(pad_edge=True)
    table.add_column("Name", no_wrap=True)  # names get copied into code; never truncate them
    table.add_column("Context", justify="right")
    table.add_column("Prompt $/1M", justify="right")
    table.add_column("Completion $/1M", justify="right")
    table.add_column("Status")
    columns = ("name", "context", "prompt-price", "completion-price", "status")
    for row in rows:
        table.add_row(*(_display(row, key) for key in columns))
    Console().print(table)


def _display(row: Dict[str, Any], key: str) -> str:
    """Render a row's value for KEY the way the table shows it (and filters compare it)."""
    value = row[_KEY_FIELDS[key]]
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _sort_key(sort_by: str) -> Any:
    field = _KEY_FIELDS[sort_by.lower()]

    def key(row: Dict[str, Any]) -> Tuple[bool, Any]:
        value = row[field]
        if isinstance(value, str):
            value = value.lower()
        return (value is None, value if value is not None else 0)

    return key


def _resolve_filters(filters: Sequence[str]) -> List[Tuple[str, str]]:
    """Flatten comma-separated and repeated --filter values into KEY=PATTERN pairs."""
    resolved = []
    for value in filters:
        for entry in _FILTER_SEPARATOR.split(value):
            raw = entry.strip()
            if not raw:
                continue
            key, separator, pattern = raw.partition("=")
            key, pattern = key.strip().lower(), pattern.strip()
            if not separator or not key:
                raise click.BadParameter(f"expected KEY=PATTERN, got {raw!r}", param_hint="'--filter'")
            if key not in _KEY_FIELDS:
                raise click.BadParameter(
                    f"unknown key {key!r}. Filter by one of: {', '.join(LIST_KEYS)}", param_hint="'--filter'"
                )
            resolved.append((key, pattern))
    return resolved


def _matches_filters(row: Dict[str, Any], filters: Sequence[Tuple[str, str]]) -> bool:
    return all(fnmatchcase(_display(row, key).lower(), pattern.lower()) for key, pattern in filters)
