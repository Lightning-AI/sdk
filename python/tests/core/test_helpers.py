import json
import os
import warnings
from unittest import mock

import pytest
from tqdm import tqdm


@mock.patch("os.isatty", return_value=False, autospec=True)
@mock.patch.dict(os.environ, {}, clear=True)
def test_tqdm_notty(_):
    from lightning_sdk.helpers import set_tqdm_envvars_noninteractive

    set_tqdm_envvars_noninteractive()

    assert "TQDM_POSITION" in os.environ
    assert os.environ["TQDM_POSITION"] == "-1"
    assert "TQDM_MININTERVAL" in os.environ
    assert os.environ["TQDM_MININTERVAL"] == "1"

    pbar = tqdm(range(10))

    assert pbar.mininterval == 1
    assert pbar.pos == 1  # pos is negative position (-(-1))


@mock.patch("os.isatty", return_value=True, autospec=True)
@mock.patch.dict(os.environ, {}, clear=True)
def test_tqdm_tty(_):
    from lightning_sdk.helpers import set_tqdm_envvars_noninteractive

    set_tqdm_envvars_noninteractive()

    assert "TQDM_POSITION" not in os.environ
    assert "TQDM_MININTERVAL" not in os.environ


class TestVersionChecker:
    """Tests for the VersionChecker class."""

    @pytest.fixture(autouse=True)
    def isolated_home(self, tmp_path, monkeypatch):
        # the version cache lives under the home directory, so keep each test's cache separate
        monkeypatch.setenv("HOME", str(tmp_path))
        return tmp_path

    def test_version_checker_initialization(self):
        """Test that VersionChecker initializes with correct default values."""
        from lightning_sdk.helpers import VersionChecker

        checker = VersionChecker()
        assert checker.package_name == "lightning-sdk"
        assert checker._warning_shown is False
        assert checker._cached_version is None

    def test_version_checker_custom_package_name(self):
        """Test that VersionChecker can be initialized with a custom package name."""
        from lightning_sdk.helpers import VersionChecker

        checker = VersionChecker(package_name="custom-package")
        assert checker.package_name == "custom-package"

    @mock.patch("lightning_sdk.helpers._LIGHTNING_DISABLE_VERSION_CHECK", 1)
    def test_version_check_disabled_by_env_var(self):
        """Test that version check is disabled when LIGHTNING_DISABLE_VERSION_CHECK=1."""
        from lightning_sdk.helpers import VersionChecker

        checker = VersionChecker()
        result = checker._get_newer_version("1.0.0")
        assert result is None
        assert checker._cached_version is None

    def test_version_check_skipped_for_prerelease(self):
        """Test that version check is skipped for prerelease versions."""
        from lightning_sdk.helpers import VersionChecker

        checker = VersionChecker()
        result = checker._get_newer_version("1.0.0rc1")
        assert result is None
        assert checker._cached_version is None

    @mock.patch("requests.get")
    def test_version_check_newer_version_available(self, mock_get):
        """Test that newer version is detected when available."""
        from lightning_sdk.helpers import VersionChecker

        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "releases": {"1.0.0": [], "2.0.0": []},
            "info": {
                "version": "2.0.0",
                "yanked": False,
            },
        }
        mock_get.return_value = mock_response

        checker = VersionChecker()
        result = checker._get_newer_version("1.0.0")
        assert result == "2.0.0"
        assert checker._cached_version == "2.0.0"

    @mock.patch("requests.get")
    def test_version_check_same_version(self, mock_get):
        """Test that None is returned when current version is latest."""
        from lightning_sdk.helpers import VersionChecker

        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "releases": {"2.0.0": []},
            "info": {
                "version": "2.0.0",
                "yanked": False,
            },
        }
        mock_get.return_value = mock_response

        checker = VersionChecker()
        result = checker._get_newer_version("2.0.0")
        assert result is None
        assert checker._cached_version is None

    @mock.patch("requests.get")
    def test_version_check_not_from_pypi(self, mock_get):
        """Test that None is returned when current version is not on PyPI (dev version)."""
        from lightning_sdk.helpers import VersionChecker

        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "releases": {"2.0.0": []},
            "info": {
                "version": "2.0.0",
                "yanked": False,
            },
        }
        mock_get.return_value = mock_response

        checker = VersionChecker()
        result = checker._get_newer_version("1.0.0.dev0")
        assert result is None
        assert checker._cached_version is None

    @mock.patch("requests.get")
    def test_version_check_yanked_version(self, mock_get):
        """Test that yanked versions are not considered as valid upgrades."""
        from lightning_sdk.helpers import VersionChecker

        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "releases": {"1.0.0": [], "2.0.0": []},
            "info": {
                "version": "2.0.0",
                "yanked": True,
            },
        }
        mock_get.return_value = mock_response

        checker = VersionChecker()
        result = checker._get_newer_version("1.0.0")
        assert result is None
        assert checker._cached_version is None

    @mock.patch("requests.get")
    def test_version_check_network_error(self, mock_get):
        """Test that network errors are handled gracefully."""
        import requests

        from lightning_sdk.helpers import VersionChecker

        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        checker = VersionChecker()
        result = checker._get_newer_version("1.0.0")
        assert result is None
        assert checker._cached_version is None

    @mock.patch("requests.get")
    def test_version_check_caching(self, mock_get):
        """Test that version check results are cached."""
        from lightning_sdk.helpers import VersionChecker

        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "releases": {"1.0.0": [], "2.0.0": []},
            "info": {
                "version": "2.0.0",
                "yanked": False,
            },
        }
        mock_get.return_value = mock_response

        checker = VersionChecker()
        # First call
        result1 = checker._get_newer_version("1.0.0")
        # Second call should use cached result
        result2 = checker._get_newer_version("1.0.0")

        assert result1 == "2.0.0"
        assert result2 == "2.0.0"
        # Verify requests.get was only called once
        assert mock_get.call_count == 1

    @mock.patch("requests.get")
    def test_warning_shown_once(self, mock_get):
        """Test that upgrade warning is only shown once per session."""
        from lightning_sdk.helpers import VersionChecker

        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "releases": {"1.0.0": [], "2.0.0": []},
            "info": {
                "version": "2.0.0",
                "yanked": False,
            },
        }
        mock_get.return_value = mock_response

        checker = VersionChecker()

        # First call should show warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            checker.check_and_prompt_upgrade("1.0.0")
            assert len(w) == 1
            assert "2.0.0" in str(w[0].message)
            assert "pip install -U lightning-sdk" in str(w[0].message)

        # Second call should NOT show warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            checker.check_and_prompt_upgrade("1.0.0")
            assert len(w) == 0

        assert checker._warning_shown is True

    @mock.patch("requests.get")
    def test_no_warning_when_no_newer_version(self, mock_get):
        """Test that no warning is shown when there is no newer version."""
        from lightning_sdk.helpers import VersionChecker

        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "releases": {"2.0.0": []},
            "info": {
                "version": "2.0.0",
                "yanked": False,
            },
        }
        mock_get.return_value = mock_response

        checker = VersionChecker()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            checker.check_and_prompt_upgrade("2.0.0")
            assert len(w) == 0

        assert checker._warning_shown is False

    @mock.patch("requests.get")
    def test_warning_message_format(self, mock_get):
        """Test that the warning message has the correct format."""
        from lightning_sdk.helpers import VersionChecker

        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "releases": {"1.0.0": [], "3.5.7": []},
            "info": {
                "version": "3.5.7",
                "yanked": False,
            },
        }
        mock_get.return_value = mock_response

        checker = VersionChecker(package_name="test-package")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            checker.check_and_prompt_upgrade("1.0.0")
            assert len(w) == 1
            message = str(w[0].message)
            assert "test-package" in message
            assert "3.5.7" in message
            assert "pip install -U test-package" in message

    @staticmethod
    def _pypi_response(latest: str = "2.0.0", releases=("1.0.0", "2.0.0")):
        response = mock.Mock()
        response.json.return_value = {
            "releases": {version: [] for version in releases},
            "info": {"version": latest, "yanked": False},
        }
        return response

    @mock.patch("requests.get")
    def test_version_check_reuses_cache_across_runs(self, mock_get):
        """A new process starts with no in-memory result but should still find the file cache."""
        from lightning_sdk.helpers import VersionChecker

        mock_get.return_value = self._pypi_response()

        assert VersionChecker()._get_newer_version("1.0.0") == "2.0.0"
        assert VersionChecker()._get_newer_version("1.0.0") == "2.0.0"
        assert mock_get.call_count == 1

    @mock.patch("requests.get")
    def test_version_check_refetches_after_a_day(self, mock_get):
        from lightning_sdk.helpers import VersionChecker

        mock_get.return_value = self._pypi_response()

        with mock.patch("lightning_sdk.helpers.time") as mock_time:
            mock_time.time.return_value = 1_000_000.0
            VersionChecker()._get_newer_version("1.0.0")
            mock_time.time.return_value = 1_000_000.0 + 24 * 60 * 60 + 1
            VersionChecker()._get_newer_version("1.0.0")

        assert mock_get.call_count == 2

    @mock.patch("requests.get")
    def test_version_check_refetches_when_installed_version_changes(self, mock_get):
        from lightning_sdk.helpers import VersionChecker

        mock_get.return_value = self._pypi_response(releases=("1.0.0", "1.5.0", "2.0.0"))

        VersionChecker()._get_newer_version("1.0.0")
        result = VersionChecker()._get_newer_version("1.5.0")

        assert result == "2.0.0"
        assert mock_get.call_count == 2

    @mock.patch("requests.get")
    def test_version_check_retries_after_network_failure(self, mock_get, isolated_home):
        """A failed check is not cached, so a machine that comes back online gets a real check."""
        import requests

        from lightning_sdk.helpers import VersionChecker

        mock_get.side_effect = requests.exceptions.RequestException("offline")

        assert VersionChecker()._get_newer_version("1.0.0") is None
        assert not (isolated_home / ".lightning" / "version_check.json").exists()

        mock_get.side_effect = None
        mock_get.return_value = self._pypi_response()

        assert VersionChecker()._get_newer_version("1.0.0") == "2.0.0"
        assert mock_get.call_count == 2

    @mock.patch("requests.get")
    def test_version_check_ignores_corrupt_cache(self, mock_get, isolated_home):
        from lightning_sdk.helpers import VersionChecker

        cache_file = isolated_home / ".lightning" / "version_check.json"
        cache_file.parent.mkdir(parents=True)
        cache_file.write_text("{not json")
        mock_get.return_value = self._pypi_response()

        assert VersionChecker()._get_newer_version("1.0.0") == "2.0.0"
        assert mock_get.call_count == 1

    @mock.patch("requests.get")
    def test_version_check_ignores_cache_timestamp_in_future(self, mock_get, isolated_home):
        from lightning_sdk.helpers import VersionChecker

        cache_file = isolated_home / ".lightning" / "version_check.json"
        cache_file.parent.mkdir(parents=True)
        cache_file.write_text(json.dumps({"current_version": "1.0.0", "newer_version": None, "checked_at": 1e12}))
        mock_get.return_value = self._pypi_response()

        assert VersionChecker()._get_newer_version("1.0.0") == "2.0.0"
        assert mock_get.call_count == 1

    @mock.patch("requests.get")
    def test_version_check_writes_cache_file(self, mock_get, isolated_home):
        from lightning_sdk.helpers import VersionChecker

        mock_get.return_value = self._pypi_response()

        VersionChecker()._get_newer_version("1.0.0")

        entry = json.loads((isolated_home / ".lightning" / "version_check.json").read_text())
        assert entry["current_version"] == "1.0.0"
        assert entry["newer_version"] == "2.0.0"
        assert isinstance(entry["checked_at"], float)
