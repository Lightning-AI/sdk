import pytest

from lightning_sdk.cli.entrypoint import main_cli
from lightning_sdk.cli.lockdown import UNAVAILABLE_COMMANDS
from lightning_sdk.cli.utils.unavailable import unmarked_command


@pytest.fixture(autouse=True)
def _fixture_run_commands_unlocked(monkeypatch):
    """Run each command's own logic, not the temporarily-unavailable notice.

    The gate is checked on the real CLI in ``test_temporarily_unavailable.py``, which overrides this fixture.
    """
    for path in UNAVAILABLE_COMMANDS:
        *parents, name = path.split()
        group = main_cli
        for parent in parents:
            group = group.commands[parent]
        monkeypatch.setitem(group.commands, name, unmarked_command(group.commands[name]))


@pytest.fixture(autouse=True)
def _fixture_disable_version_check(monkeypatch):
    """Silence version-check noise for CLI subprocesses."""
    monkeypatch.setenv("LIGHTNING_DISABLE_VERSION_CHECK", "1")


@pytest.fixture(autouse=True)
def _fixture_no_command_telemetry(monkeypatch):
    """Don't POST CLI command history to the API: unit tests must not need network access."""
    monkeypatch.setattr("lightning_sdk.cli.utils.logging._log_command", lambda *args, **kwargs: None)
