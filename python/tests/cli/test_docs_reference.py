"""Every visible top-level CLI command has a page in the CLI reference docs.

A command only reaches the published reference when docs/cli has a page whose
``lightning-reference`` directive renders it and index.rst lists that page.
Nothing else checks that, so new command groups shipped undocumented.
"""

import importlib
import re
from pathlib import Path

from lightning_sdk.cli.entrypoint import main_cli

DOCS_CLI = Path(__file__).resolve().parents[2] / "docs" / "cli"

# Documented on the index page itself, which renders the root command.
ON_INDEX_PAGE = {"login", "logout", "completion"}

_DIRECTIVE = re.compile(r"^\.\. lightning-reference:: (\w+)$", re.MULTILINE)
_IMPORT = re.compile(r"^\s+from ([\w.]+) import (\w+)$", re.MULTILINE)


def _reference_pages() -> dict[str, str]:
    """Map each documented command's name to the page that renders it."""
    pages = {}
    for page in sorted(DOCS_CLI.glob("*.rst")):
        if page.name == "index.rst":
            continue
        text = page.read_text()
        directive = _DIRECTIVE.search(text)
        if not directive:
            continue
        imports = {name: module for module, name in _IMPORT.findall(text)}
        obj = directive.group(1)
        assert obj in imports, f"{page.name}: no import for {obj!r}"
        command = getattr(importlib.import_module(imports[obj]), obj)
        pages[command.name] = page.stem
    return pages


def _toctree_entries() -> set[str]:
    index = (DOCS_CLI / "index.rst").read_text()
    toctree = index.split(".. toctree::", 1)[1]
    return {line.strip() for line in toctree.splitlines()[1:] if line.startswith("   ") and ":" not in line}


def test_every_visible_command_has_a_reference_page():
    visible = {name for name, command in main_cli.commands.items() if not command.hidden}
    documented = set(_reference_pages())
    missing = sorted(visible - documented - ON_INDEX_PAGE)
    assert not missing, (
        f"No page in docs/cli for: {', '.join(missing)}. Add one like docs/cli/cp.rst and list it in index.rst."
    )


def test_every_reference_page_is_in_the_index():
    unlisted = sorted(set(_reference_pages().values()) - _toctree_entries())
    assert not unlisted, f"Pages missing from the index.rst toctree: {', '.join(unlisted)}"
