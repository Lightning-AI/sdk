#!/usr/bin/env python3
"""Tests for go_release_tag.py. Run with ``python .github/scripts/test_go_release_tag.py``."""

import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from go_release_tag import go_tag  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "go_release_tag.py"

# Every release tag published so far, in release order. It covers each tag
# shape in use: no suffix, ".postN", "postN" without the dot, and a day with
# both a base release and post releases.
RELEASE_TAGS = [
    "v2026.07.03",
    "v2026.07.07",
    "v2026.07.07.post1",
    "v2026.07.08",
    "v2026.07.09",
    "v2026.07.09.post0",
    "v2026.07.21",
    "v2026.07.21.post0",
    "v2026.07.22",
    "v2026.07.31",
    "v2026.08.05",
    "v2026.08.14",
    "v2026.08.18",
    "v2026.08.26",
    "v2026.09.02",
    "v2026.09.03",
    "v2026.09.15",
    "v2026.09.18",
    "v2026.09.18.post1",
    "v2026.10.01",
    "v2026.10.13",
    "v2026.10.27",
    "v2026.11.02",
    "v2026.11.03",
    "v2026.11.04",
    "v2026.11.04.post0",
    "v2026.11.04.post1",
    "v2026.11.05",
    "v2026.11.06",
    "v2026.11.10",
    "v2026.11.10post0",
    "v2026.11.13",
]

# Go accepts vMAJOR.MINOR.PATCH with no leading zeros in any number.
GO_SEMVER = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


def go_version(release_tag):
    tag = go_tag(release_tag)
    assert tag is not None and tag.startswith("go/"), (release_tag, tag)
    return tag[len("go/") :]


class GoReleaseTagTest(unittest.TestCase):
    def test_examples(self):
        cases = {
            "v2026.11.13": "go/v0.20261113.0",
            "v2026.11.10": "go/v0.20261110.0",
            "v2026.11.10post0": "go/v0.20261110.1",
            "v2026.11.04.post0": "go/v0.20261104.1",
            "v2026.11.04.post1": "go/v0.20261104.2",
            "v2026.07.07.post1": "go/v0.20260707.2",
            "v2026.11.04.post12": "go/v0.20261104.13",
        }
        for release_tag, expected in cases.items():
            with self.subTest(release_tag=release_tag):
                self.assertEqual(go_tag(release_tag), expected)

    def test_release_tags_map_to_valid_go_versions(self):
        for release_tag in RELEASE_TAGS:
            with self.subTest(release_tag=release_tag):
                self.assertRegex(go_version(release_tag), f"^{GO_SEMVER.pattern}$")

    def test_go_versions_increase_in_release_order(self):
        versions = [
            tuple(int(n) for n in GO_SEMVER.fullmatch(go_version(t)).groups())
            for t in RELEASE_TAGS
        ]
        for i in range(1, len(RELEASE_TAGS)):
            with self.subTest(previous=RELEASE_TAGS[i - 1], tag=RELEASE_TAGS[i]):
                self.assertLess(versions[i - 1], versions[i])

    def test_other_tags_are_skipped(self):
        for tag in [
            "v2026.11.13rc1",
            "v2026.11.13-rc.1",
            "v2026.11.13.dev0",
            "v2026.11.13.post",
            "v2026.11.13.post01",
            "v2026.11.13.0",
            "v2026.13.01",
            "v2026.02.30",
            "v0999.01.01",
            "v2026.1.13",
            "2026.11.13",
            "go/v0.20261113.0",
            "main",
            "",
        ]:
            with self.subTest(tag=tag):
                self.assertIsNone(go_tag(tag))

    def test_cli(self):
        def run(*args):
            return subprocess.run(
                [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
            )

        mapped = run("v2026.11.10post0")
        self.assertEqual((mapped.returncode, mapped.stdout), (0, "go/v0.20261110.1\n"))

        skipped = run("v2026.11.13rc1")
        self.assertEqual((skipped.returncode, skipped.stdout), (0, ""))
        self.assertIn("v2026.11.13rc1", skipped.stderr)

        self.assertEqual(run().returncode, 2)


if __name__ == "__main__":
    unittest.main()
