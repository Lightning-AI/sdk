import importlib
import os
import sys
import warnings
from typing import Optional

import requests
import tqdm
import tqdm.std
from packaging import version as packaging_version

from lightning_sdk.constants import _LIGHTNING_DISABLE_VERSION_CHECK


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

        The result is cached after the first successful network call.

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

        try:
            response = requests.get(f"https://pypi.org/pypi/{self.package_name}/json")
            response_json = response.json()
            releases = response_json["releases"]
            if curr_version not in releases:
                # Always return None if not installed from PyPI (e.g. dev versions)
                self._cached_version = None
                return None
            latest_version = response_json["info"]["version"]
            parsed_version = packaging_version.parse(latest_version)
            is_invalid = response_json["info"]["yanked"] or parsed_version.is_devrelease or parsed_version.is_prerelease
            self._cached_version = None if curr_version == latest_version or is_invalid else latest_version
            return self._cached_version
        except requests.exceptions.RequestException:
            self._cached_version = None
            return None

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
