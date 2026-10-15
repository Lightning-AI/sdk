"""Shared ``--filter KEY=PATTERN`` parsing and matching for list commands."""

import re
from fnmatch import fnmatchcase
from typing import Callable, Sequence, Tuple

import rich_click as click

Filters = Tuple[Tuple[str, str], ...]


def resolve_filters(filters: Sequence[str], keys: Sequence[str]) -> Filters:
    """Flatten comma-separated and repeated --filter values into KEY=PATTERN pairs.

    Keys outside ``keys`` (the same set `--sort-by` accepts) are rejected, which keeps the two options in parity.
    """
    # Only a comma that introduces the next pair separates filters; one inside a pattern
    # (`name=job-[0,1]`) or a value (an image tag) belongs to that pattern.
    separator = re.compile(r",(?=\s*(?:" + "|".join(re.escape(key) for key in keys) + r")\s*=)")

    resolved = []
    for value in filters:
        for entry in separator.split(value):
            raw = entry.strip()
            if not raw:
                continue

            key, equals, pattern = raw.partition("=")
            key, pattern = key.strip().lower(), pattern.strip()
            if not equals or not key:
                raise click.BadParameter(f"expected KEY=PATTERN, got {raw!r}", param_hint="'--filter'")
            if key not in keys:
                raise click.BadParameter(
                    f"unknown key {key!r}. Filter by one of: {', '.join(keys)}", param_hint="'--filter'"
                )
            resolved.append((key, pattern))

    return tuple(resolved)


def matches_filters(display: Callable[[str], str], filters: Filters) -> bool:
    """Whether every filter's case-insensitive glob matches ``display(key)``, the value as shown."""
    return all(fnmatchcase(display(key).lower(), pattern.lower()) for key, pattern in filters)
