"""File helpers shared by the coding tools, and the record of what `lightning code` set up."""

import json
import os
import stat
from pathlib import Path
from typing import Any, Optional

BACKUP_SUFFIX = ".lightning-backup"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object, or {} when the file is missing or empty. Raises ValueError otherwise."""
    text = read_text(path)
    if not text.strip():
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def dump_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2) + "\n"


def write_text(path: Path, text: str, *, mode: Optional[int] = None) -> None:
    """Replace ``path`` atomically, keeping its permissions unless ``mode`` is given."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    tmp = path.with_name(f".{path.name}.lightning-tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def delete(path: Path) -> None:
    path.unlink(missing_ok=True)


def records_path() -> Path:
    """Where `lightning code` marks the tools it set up, for tools that have no place for the mark."""
    return Path.home() / ".lightning" / "code-tools.json"


def is_managed(tool: str) -> bool:
    try:
        return tool in read_json(records_path())
    except ValueError:
        return False


def records_text(tool: str, managed: bool) -> tuple[str, str]:
    """The record file before and after marking ``tool`` as set up by `lightning code`, or unmarking it."""
    before = read_text(records_path())
    try:
        data = read_json(records_path())
    except ValueError:
        data = {}
    if managed:
        data[tool] = {"managed": True}
    else:
        data.pop(tool, None)
    return before, dump_json(data)
