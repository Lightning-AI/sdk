"""Read and edit JSONC (JSON with comments and trailing commas) without reformatting it.

Edits splice text into the original document, so everything outside the edited member
(comments, key order, indentation) stays byte-for-byte the same.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence


class JSONCError(ValueError):
    """The document is not valid JSONC."""


@dataclass
class _Member:
    key: str
    start: int
    end: int
    value: "_Node"


@dataclass
class _Node:
    start: int
    end: int
    kind: str  # "object", "array" or "scalar"
    members: list[_Member] = field(default_factory=list)

    def member(self, key: str) -> Optional[_Member]:
        return next((m for m in self.members if m.key == key), None)


class _Parser:
    def __init__(self, text: str, pos: int = 0) -> None:
        self.text = text
        self.pos = pos

    def fail(self, message: str) -> JSONCError:
        line = self.text.count("\n", 0, self.pos) + 1
        return JSONCError(f"{message} at line {line}")

    def skip(self) -> None:
        """Skip whitespace and comments."""
        text = self.text
        while self.pos < len(text):
            if text[self.pos] in " \t\r\n﻿":
                self.pos += 1
            elif text.startswith("//", self.pos):
                newline = text.find("\n", self.pos)
                self.pos = len(text) if newline < 0 else newline + 1
            elif text.startswith("/*", self.pos):
                close = text.find("*/", self.pos + 2)
                if close < 0:
                    raise self.fail("unterminated comment")
                self.pos = close + 2
            else:
                return

    def peek(self) -> str:
        self.skip()
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def string(self) -> str:
        start = self.pos
        self.pos += 1
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\\":
                self.pos += 2
            elif char == '"':
                self.pos += 1
                return json.loads(self.text[start : self.pos])
            else:
                self.pos += 1
        raise self.fail("unterminated string")

    def value(self) -> _Node:
        char = self.peek()
        start = self.pos
        if char == "{":
            return self.obj()
        if char == "[":
            return self.array()
        if char == '"':
            self.string()
            return _Node(start, self.pos, "scalar")
        while self.pos < len(self.text) and self.text[self.pos] not in ',:[]{}/" \t\r\n':
            self.pos += 1
        if self.pos == start:
            raise self.fail("expected a value")
        return _Node(start, self.pos, "scalar")

    def obj(self) -> _Node:
        node = _Node(self.pos, self.pos, "object")
        self.pos += 1
        while True:
            char = self.peek()
            if char == "}":
                self.pos += 1
                node.end = self.pos
                return node
            if char != '"':
                raise self.fail("expected a key")
            start = self.pos
            key = self.string()
            if self.peek() != ":":
                raise self.fail("expected ':'")
            self.pos += 1
            value = self.value()
            node.members.append(_Member(key, start, value.end, value))
            char = self.peek()
            if char == ",":
                self.pos += 1
            elif char != "}":
                raise self.fail("expected ',' or '}'")

    def array(self) -> _Node:
        node = _Node(self.pos, self.pos, "array")
        self.pos += 1
        while True:
            char = self.peek()
            if char == "]":
                self.pos += 1
                node.end = self.pos
                return node
            self.value()
            char = self.peek()
            if char == ",":
                self.pos += 1
            elif char != "]":
                raise self.fail("expected ',' or ']'")


def _parse(text: str) -> _Node:
    parser = _Parser(text)
    if parser.peek() == "":
        raise JSONCError("empty document")
    root = parser.value()
    if parser.peek() != "":
        raise parser.fail("unexpected content after the document")
    return root


def _strip(text: str) -> str:
    """Return ``text`` as plain JSON: comments blanked out and trailing commas dropped."""
    out: list[str] = []
    parser = _Parser(text)
    comma: Optional[int] = None
    while True:
        before = parser.pos
        parser.skip()
        out.append(" " * (parser.pos - before))
        if parser.pos >= len(text):
            return "".join(out)
        if text[parser.pos] == '"':
            start = parser.pos
            parser.string()
            token = text[start : parser.pos]
        else:
            token = text[parser.pos]
            parser.pos += 1
        if token in "]}" and comma is not None:
            out[comma] = " "
        comma = len(out) if token == "," else None
        out.append(token)


def loads(text: str) -> Any:
    """Parse a JSONC document into Python values."""
    _parse(text)
    try:
        return json.loads(_strip(text))
    except json.JSONDecodeError as exc:
        raise JSONCError(str(exc)) from None


def _line_start(text: str, pos: int) -> int:
    return text.rfind("\n", 0, pos) + 1


def _line_indent(text: str, pos: int) -> str:
    line = text[_line_start(text, pos) : pos]
    return line[: len(line) - len(line.lstrip(" \t"))]


def _starts_line(text: str, pos: int) -> bool:
    return not text[_line_start(text, pos) : pos].strip()


def _line_rest(text: str, pos: int) -> int:
    """Skip spaces and a ``//`` comment after ``pos``, stopping before the newline."""
    while pos < len(text) and text[pos] in " \t":
        pos += 1
    if text.startswith("//", pos):
        newline = text.find("\n", pos)
        pos = len(text) if newline < 0 else newline
    return pos


def _indent_unit(text: str) -> str:
    for line in text.splitlines()[1:]:
        stripped = line.lstrip(" \t")
        if stripped and line != stripped:
            return line[: len(line) - len(stripped)]
    return "  "


def _render(value: Any, indent: str, unit: str) -> str:
    return json.dumps(value, indent=unit, ensure_ascii=False).replace("\n", "\n" + indent)


def _object_at(root: _Node, path: Sequence[str]) -> tuple[_Node, int]:
    """Return the deepest object along ``path`` and how many keys of ``path`` it consumed."""
    node, depth = root, 0
    for key in path:
        member = node.member(key)
        if member is None or member.value.kind != "object":
            break
        node, depth = member.value, depth + 1
    return node, depth


def _root(text: str) -> _Node:
    root = _parse(text)
    if root.kind != "object":
        raise JSONCError("the document is not a JSON object")
    return root


def get_value(text: str, path: Sequence[str], default: Any = None) -> Any:
    """Return the value at ``path``, or ``default`` when it is not set."""
    value = loads(text) if text.strip() else {}
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def set_value(text: str, path: Sequence[str], value: Any) -> str:
    """Set ``path`` to ``value``, creating missing objects along it, and return the new text."""
    if not path:
        raise ValueError("path must not be empty")
    if not text.strip():
        text = "{}\n"
    unit = _indent_unit(text)
    node, depth = _object_at(_root(text), path[:-1])

    member = node.member(path[depth])
    if member is not None:
        if depth < len(path) - 1:
            raise JSONCError(f"'{'.'.join(path[: depth + 1])}' is not an object")
        rendered = _render(value, _line_indent(text, member.start), unit)
        return text[: member.value.start] + rendered + text[member.value.end :]

    # the missing tail of the path becomes one nested value, inserted as a new member
    for key in reversed(path[depth + 1 :]):
        value = {key: value}
    key = json.dumps(path[depth])

    if node.members:
        last = node.members[-1]
        parser = _Parser(text, last.end)
        has_comma = parser.peek() == ","
        after = parser.pos + 1 if has_comma else last.end
        if not _starts_line(text, last.start):
            rendered = f" {key}: {_render(value, _line_indent(text, last.start), unit)}"
            return text[:after] + ("" if has_comma else ",") + rendered + ("," if has_comma else "") + text[after:]
        indent = _line_indent(text, last.start)
        insert_at = _line_rest(text, after)
        rendered = f"\n{indent}{key}: {_render(value, indent, unit)}" + ("," if has_comma else "")
        text = text[:insert_at] + rendered + text[insert_at:]
        return text if has_comma else text[: last.end] + "," + text[last.end :]

    close = node.end - 1
    outer = _line_indent(text, node.start)
    inner = text[node.start + 1 : close].rstrip(" \t")
    if not inner.endswith("\n"):
        inner += "\n"
    rendered = f"{outer}{unit}{key}: {_render(value, outer + unit, unit)}\n{outer}"
    return text[: node.start + 1] + inner + rendered + text[close:]


def remove_value(text: str, path: Sequence[str]) -> str:
    """Remove the member at ``path`` when it exists, and return the new text."""
    if not path or not text.strip():
        return text
    node, depth = _object_at(_root(text), path[:-1])
    if depth != len(path) - 1:
        return text
    index = next((i for i, m in enumerate(node.members) if m.key == path[-1]), None)
    if index is None:
        return text
    member = node.members[index]
    own_line = _starts_line(text, member.start)

    parser = _Parser(text, member.end)
    if parser.peek() == ",":
        # drop the member through its comma, and its whole line when it had one to itself
        start = _line_start(text, member.start) if own_line else member.start
        end = _line_rest(text, parser.pos + 1)
        if own_line and text.startswith("\n", end):
            end += 1
        return text[:start] + text[end:]

    # the last member: drop it along with its line, then the comma the member before it ended with
    start = _line_start(text, member.start) - 1 if own_line else member.start
    end = _line_rest(text, member.end)
    if index == 0:
        inner = text[node.start + 1 : start] + text[end : node.end - 1]
        if not inner.strip():
            return text[: node.start + 1] + text[node.end - 1 :]
        return text[:start] + text[end:]

    previous = _Parser(text, node.members[index - 1].end)
    previous.peek()
    comma = previous.pos
    text = text[:start] + text[end:]
    return text[:comma] + text[comma + 1 :]
