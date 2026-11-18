import multiprocessing
import os
import queue
import time

import keyring
import pytest

from lightning_sdk.lightning_cloud import cli_login, env
from tests.lightning_cloud.utils import login_worker
from tests.lightning_cloud.utils.keyrings import KEYRING_PATH, FileKeyring

_PROCESSES = 8


@pytest.fixture()
def _shared_keyring(tmp_path, monkeypatch):
    monkeypatch.setenv(KEYRING_PATH, str(tmp_path / "keyring.json"))
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "tests.lightning_cloud.utils.keyrings.FileKeyring")
    keyring.set_keyring(FileKeyring())


def _run(target, args_for):
    """Run ``target`` in fresh processes and return what each reported."""
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    # Process.start() drops its args, and a spawned child can only open a
    # barrier the parent still holds.
    shared = args_for(context)
    processes = [context.Process(target=target, args=(*args, results)) for args in shared]
    for process in processes:
        process.start()
    try:
        reports = []
        deadline = time.monotonic() + 90
        for _ in processes:
            try:
                reports.append(results.get(timeout=max(deadline - time.monotonic(), 0.1)))
            except queue.Empty:
                break
        for process in processes:
            process.join(timeout=max(deadline - time.monotonic(), 0.1))
    finally:
        for process in processes:
            if process.is_alive():
                process.kill()
    errors = [detail for status, detail in reports if status != "ok"]
    assert errors == []
    assert len(reports) == len(processes)
    assert [process.exitcode for process in processes] == [0] * len(processes)
    return [detail for _, detail in reports]


def test_eight_processes_share_one_login_through_several_refreshes_without_reuse(platform, browser, _shared_keyring):
    # Anything under five minutes left is refreshed, so each token lasts one second.
    platform.access_ttl = 301
    cli_login.login()

    def args_for(context):
        barrier = context.Barrier(_PROCESSES)
        return [(barrier, 4.0)] * _PROCESSES

    calls = _run(login_worker.call_the_api, args_for)

    assert all(count > 0 for count in calls)
    assert platform.reuse_events == []
    assert 3 <= len(platform.refreshes()) <= 10
    assert platform.family_active(cli_login.token(min_remaining=0))


def test_a_fresh_process_repairs_a_save_interrupted_between_keychain_and_login_file(
    platform, browser, _shared_keyring, monkeypatch
):
    cli_login.login()
    real_replace = os.replace

    def crash_on_the_login_file(source, target):
        if os.fspath(target) == env.LIGHTNING_LOGIN_PATH:
            raise OSError("the process died here")
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", crash_on_the_login_file)
    with pytest.raises(OSError, match="the process died here"):
        cli_login.token(min_remaining=10 * 3600)
    monkeypatch.setattr(os, "replace", real_replace)

    [printed] = _run(login_worker.take_a_token, lambda context: [()])

    assert platform.accepts(printed)
    assert platform.reuse_events == []
    assert len(platform.refreshes()) == 2
    status = cli_login.current_login()
    assert status.access_expires_at == pytest.approx(time.time() + 3600, abs=60)
    assert cli_login.token() == printed
