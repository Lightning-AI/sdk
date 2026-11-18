#!/usr/bin/env python3
"""Map a release tag to the tag that versions the Go module in ``go/``.

Go versions a module in a subdirectory only through tags prefixed with that
directory, and only reads semantic versions. Each release tag (see RELEASE.md)
therefore gets a matching Go tag:

    vYYYY.MM.DD                          -> go/v0.YYYYMMDD.0
    vYYYY.MM.DD.postN or vYYYY.MM.DDpostN -> go/v0.YYYYMMDD.(N+1)

``postN`` maps to patch N+1 because the day's first release already takes patch
0. Major version 0 keeps the module path free of a ``/vN`` suffix.

Usage: go_release_tag.py <release tag>

Prints the Go tag, or prints nothing and explains why on stderr when the tag is
not a release tag, such as a pre-release.
"""

import datetime
import re
import sys
from typing import Optional

_RELEASE_TAG = re.compile(r"v([1-9]\d{3})\.(\d{2})\.(\d{2})(?:\.?post(0|[1-9]\d*))?")


def go_tag(release_tag: str) -> Optional[str]:
    """Return the Go tag for ``release_tag``, or None if it is not a release tag."""
    match = _RELEASE_TAG.fullmatch(release_tag)
    if match is None:
        return None
    year, month, day, post = match.groups()
    try:
        datetime.date(int(year), int(month), int(day))
    except ValueError:
        return None
    patch = 0 if post is None else int(post) + 1
    return f"go/v0.{year}{month}{day}.{patch}"


def main(argv: list) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <release tag>", file=sys.stderr)
        return 2
    tag = go_tag(argv[1])
    if tag is None:
        print(
            f"{argv[1]!r} is not a vYYYY.MM.DD[.postN] release tag, so it gets no Go tag.",
            file=sys.stderr,
        )
    else:
        print(tag)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
