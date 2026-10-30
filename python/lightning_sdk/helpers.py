import importlib
import json
import os
import sys
import time
import warnings
from contextlib import suppress
from pathlib import Path
from typing import Optional

import requests
import tqdm
import tqdm.std
from packaging import version as packaging_version

from lightning_sdk.constants import _LIGHTNING_DISABLE_VERSION_CHECK

_VERSION_CHECK_TIMEOUT_SECONDS = 2
# the PyPI lookup runs at most once per this interval; the result is kept on disk in between
_VERSION_CHECK_INTERVAL_SECONDS = 24 * 60 * 60


def _version_cache_path() -> Path:
    return Path.home() / ".lightning" / "version_check.json"


def _read_version_cache(curr_version: str) -> Optional[dict]:
    """The cached check for ``curr_version`` if it is fresh, else ``None``."""
    try:
        entry = json.loads(_version_cache_path().read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(entry, dict) or entry.get("current_version") != curr_version:
        return None
    checked_at = entry.get("checked_at")
    newer_version = entry.get("newer_version")
    if not isinstance(checked_at, (int, float)) or not (newer_version is None or isinstance(newer_version, str)):
        return None
    # a timestamp in the future would otherwise keep the entry alive indefinitely
    if not 0 <= time.time() - checked_at < _VERSION_CHECK_INTERVAL_SECONDS:
        return None
    return entry


def _write_version_cache(curr_version: str, newer_version: Optional[str]) -> None:
    """Record the outcome of a check. Failing to write it only costs a repeated check next time."""
    path = _version_cache_path()
    entry = {"current_version": curr_version, "newer_version": newer_version, "checked_at": time.time()}
    with suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        # write to a per-process file and rename, so concurrent commands never read a partial file
        tmp_path = path.with_suffix(f".{os.getpid()}.tmp")
        tmp_path.write_text(json.dumps(entry))
        os.replace(tmp_path, path)


class VersionChecker:
    """Handles version checking and upgrade prompts for lightning-sdk.

    This class ensures that version check warnings are only shown once per session,
    preventing duplicate warnings in multithreaded scenarios.
    """

    def __init__(self, package_name: str = "lightning-sdk") -> None:
        self.package_name = package_name
        self._warning_shown = False
        self._cached_version: Optional[str] = None

    def _get_newer_version(self, curr_version: str) -> Optional[str]:
        """Check PyPI for a newer stable release of ``lightning-sdk``.

        The result is kept in ``~/.lightning/version_check.json`` for a day, so most runs make no request.

        Args:
            curr_version: The currently installed version string (e.g. ``"0.9.0"``).

        Returns:
            Optional[str]: The latest stable version if it differs from ``curr_version``,
            or ``None`` if the current version is up to date, not from PyPI, or the check
            is disabled.
        """
        if self._cached_version is not None:
            return self._cached_version

        if _LIGHTNING_DISABLE_VERSION_CHECK == 1 or packaging_version.parse(curr_version).is_prerelease:
            self._cached_version = None
            return None

        cached = _read_version_cache(curr_version)
        if cached is not None:
            self._cached_version = cached["newer_version"]
            return self._cached_version

        try:
            newer_version = self._fetch_newer_version(curr_version)
        except requests.exceptions.RequestException:
            # not cached, so the next run tries PyPI again once the network is back
            self._cached_version = None
            return None
        _write_version_cache(curr_version, newer_version)
        self._cached_version = newer_version
        return newer_version

    def _fetch_newer_version(self, curr_version: str) -> Optional[str]:
        """Ask PyPI for the latest release. Raises ``requests.RequestException`` if PyPI can't be reached."""
        # runs on every import until the result is cached, so a stalled PyPI must not hold up the command
        response = requests.get(
            f"https://pypi.org/pypi/{self.package_name}/json", timeout=_VERSION_CHECK_TIMEOUT_SECONDS
        )
        response_json = response.json()
        releases = response_json["releases"]
        if curr_version not in releases:
            # Always return None if not installed from PyPI (e.g. dev versions)
            return None
        latest_version = response_json["info"]["version"]
        parsed_version = packaging_version.parse(latest_version)
        is_invalid = response_json["info"]["yanked"] or parsed_version.is_devrelease or parsed_version.is_prerelease
        return None if curr_version == latest_version or is_invalid else latest_version

    def check_and_prompt_upgrade(self, curr_version: str) -> None:
        """Emit a ``UserWarning`` if a newer ``lightning-sdk`` release is available on PyPI.

        The warning is only emitted once per instance to avoid duplicate messages in
        multi-threaded scenarios.

        Args:
            curr_version: The currently installed version string.
        """
        if self._warning_shown:
            return

        new_version = self._get_newer_version(curr_version)
        if new_version:
            warnings.warn(
                f"A newer version of {self.package_name} is available ({new_version}). "
                f"Please consider upgrading with `pip install -U {self.package_name}`. "
                "Not all platform functionality can be guaranteed to work with the current version.",
                UserWarning,
            )
            self._warning_shown = True


def set_tqdm_envvars_noninteractive() -> None:
    """Configure tqdm environment variables for non-interactive (CI/headless) environments.

    In TTY environments the env vars are cleared so tqdm uses its defaults.
    In non-TTY environments ``TQDM_POSITION=-1`` and ``TQDM_MININTERVAL=1`` are set
    to avoid cluttered progress-bar output in log files.
    """
    # note: stderr is the default stream tqdm writes progressbars to
    # so we check that one.
    if os.isatty(sys.stderr.fileno()):
        os.unsetenv("TQDM_POSITION")
        os.unsetenv("TQDM_MININTERVAL")
    else:
        # makes use of https://github.com/tqdm/tqdm/blob/master/tqdm/utils.py#L34 to set defaults
        os.environ.update({"TQDM_POSITION": "-1", "TQDM_MININTERVAL": "1"})

    # reload to make sure env vars are parsed again
    importlib.reload(tqdm.std)
    importlib.reload(tqdm)
