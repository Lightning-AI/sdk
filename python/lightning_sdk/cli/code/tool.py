"""What every coding tool `lightning code` sets up provides, and the steps they share.

A tool reads its current state, then plans the file changes for a setup or removal as
text, before and after. The commands show those plans for --dry-run and apply them, so
each tool only decides what its files should say.
"""

import difflib
import re
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from lightning_sdk.cli.code import files
from lightning_sdk.cli.code.models import CodingModel, default_model

_KEY_PATTERN = re.compile(r"sk-lit-[A-Za-z0-9_-]+")


def _redact(text: str) -> str:
    return _KEY_PATTERN.sub("sk-lit-…", text)


class ToolConfigError(Exception):
    """A tool's config can't be read, so it isn't safe to change."""


@dataclass
class KeyRecord:
    """The org and API key `lightning code` set a tool up with."""

    org_id: str
    org_name: str
    key_id: str
    key_name: str

    def as_dict(self) -> dict[str, str]:
        return {"org_id": self.org_id, "org_name": self.org_name, "key_id": self.key_id, "key_name": self.key_name}

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> Optional["KeyRecord"]:
        if not data or not all(isinstance(data.get(k), str) for k in ("org_id", "key_id")):
            return None
        return cls(data["org_id"], data.get("org_name") or "", data["key_id"], data.get("key_name") or data["key_id"])


@dataclass
class ToolState:
    """What a tool's files say about its Lightning setup right now."""

    # what `lightning code` set up, if it did
    record: Optional[KeyRecord]
    # the API key the tool holds now, when it can be read back
    key: Optional[str]
    # Lightning is set up in the tool, by anyone
    configured: bool
    default_model: Optional[str]
    # where the setup lives, for messages
    location: str
    # anything else the tool needs to plan from its state
    data: Any = None

    @property
    def foreign(self) -> bool:
        """Whether a Lightning setup exists that `lightning code` didn't write."""
        return self.configured and self.record is None


@dataclass
class FileChange:
    path: Path
    before: str
    # None deletes the file
    after: Optional[str]
    mode: Optional[int] = None
    # holds the API key, so --dry-run masks it
    secret: bool = False
    # a copy is kept before a file the user already had is changed, unless it holds keys
    backup: bool = True
    # our own bookkeeping, not worth showing in --dry-run
    quiet: bool = False
    # shown by --dry-run instead of a diff, for files that hold other credentials too
    summary: Optional[str] = None

    @property
    def changed(self) -> bool:
        return self.before != (self.after or "") or (self.after is None and self.path.exists())

    def describe(self) -> str:
        if not self.changed:
            return ""
        if self.after is None:
            return f"Would delete {self.path}\n"
        if self.summary:
            return f"Would {self.summary} in {self.path}\n"
        before, after = self.before, self.after
        if self.secret:
            before, after = _redact(before), _redact(after)
        lines = difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(self.path),
            tofile=str(self.path),
        )
        return "".join(lines)


@dataclass
class Plan:
    changes: list[FileChange] = field(default_factory=list)
    # the default model the setup sets, if it sets one
    set_model: Optional[str] = None
    # what a removal takes out, for messages
    removed: list[str] = field(default_factory=list)

    def describe(self) -> str:
        return "".join(change.describe() for change in self.changes if not change.quiet)


def record_change(tool: str, record: Optional[KeyRecord]) -> FileChange:
    """The change to the shared record file that notes, or forgets, ``tool``'s org and key."""
    before, after = files.records_text(tool, record.as_dict() if record else None)
    return FileChange(files.records_path(), before, after, mode=0o600, backup=False, quiet=True)


def apply(plan: Plan) -> list[Path]:
    """Write a plan's changes, backing up the user's files first. Returns the backups made."""
    backups = []
    for change in plan.changes:
        if not change.changed:
            continue
        # files holding keys aren't copied, so no second copy of anyone's secrets is left around
        if change.backup and not change.secret and change.before and change.path.exists():
            backup = change.path.with_name(change.path.name + files.BACKUP_SUFFIX)
            shutil.copy2(change.path, backup)
            backups.append(backup)
        if change.after is None:
            files.delete(change.path)
        else:
            files.write_text(change.path, change.after, mode=change.mode)
    return backups


class Tool(ABC):
    """A coding tool `lightning code` can point at code.lightning.ai."""

    id: str
    name: str
    # the executable to look for on PATH, and how to install it
    binary: Optional[str] = None
    install: Optional[str] = None
    # how to start using it once set up
    start: str = ""

    @abstractmethod
    def read(self) -> ToolState:
        """Read the tool's config. Raises ToolConfigError when it can't be parsed."""

    @abstractmethod
    def plan_setup(
        self,
        state: ToolState,
        *,
        models: Sequence[CodingModel],
        model: Optional[str],
        key: str,
        record: KeyRecord,
    ) -> Plan:
        """The changes that point the tool at code.lightning.ai with ``key``.

        ``model`` is a model key from --model. Without it, a tool sets the default model only
        where the user has none, or has one on a Lightning model that's no longer served.
        """

    @abstractmethod
    def plan_remove(self, state: ToolState) -> Plan:
        """The changes that take Lightning out of the tool again."""

    def summary(self, state: ToolState, plan: Plan) -> list[tuple[str, str]]:
        """Labelled lines describing a finished setup."""
        return []

    def instructions(self, key: str, models: Sequence[CodingModel], plan: Plan) -> Optional[str]:
        """Steps the user still has to take by hand after setup, with the new key, if any."""
        return None

    def removal_instructions(self) -> Optional[str]:
        return None

    def warnings(self, state: ToolState) -> list[str]:
        """Settings elsewhere that would stop the tool from using the setup."""
        return []

    def installed(self) -> bool:
        return self.binary is None or shutil.which(self.binary) is not None


def default_to_set(
    current: Optional[str],
    *,
    requested: Optional[str],
    models: Sequence[CodingModel],
    ref: Callable[[CodingModel], str],
    ours: Callable[[str], bool],
) -> Optional[str]:
    """The default model a setup should set, in the tool's own reference format, or None to leave it.

    --model always wins. Otherwise the default is set only when the user has none, or has one
    on a Lightning model (``ours``) that is no longer served.
    """
    by_key = {model.key: model for model in models}
    if requested is not None:
        return ref(by_key[requested])
    if current is None or (ours(current) and current not in {ref(model) for model in models}):
        return ref(by_key[default_model(tuple(models))])
    return None


def emptied(text: str, *, ignore: Sequence[str] = ()) -> Optional[str]:
    """``text``, or None (delete the file) when a removal left a JSON object with nothing in it, not even comments.

    ``ignore`` names keys that don't count, such as a ``$schema`` setup added to a new file.
    """
    from lightning_sdk.utils import jsonc

    try:
        data = jsonc.loads(text) if text.strip() else {}
    except jsonc.JSONCError:
        return text
    if jsonc.has_comments(text):
        # the user's comments are worth keeping the file for
        return text
    if isinstance(data, dict) and not {k: v for k, v in data.items() if k not in ignore and v != {}}:
        return None
    return text
