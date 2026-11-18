"""Code a spawned process runs on the login its parent test made.

The parent passes LIGHTNING_CLOUD_URL, LIGHTNING_LOGIN_PATH and a shared
keyring through the environment.
"""
import time
import webbrowser


def _refuse_browser(url, *args, **kwargs):
    raise AssertionError("a worker opened the real browser")


def call_the_api(barrier, seconds, results):
    webbrowser.open = _refuse_browser
    try:
        from lightning_sdk.lightning_cloud.rest_client import GridRestClient

        client = GridRestClient()
        barrier.wait(timeout=60)
        deadline = time.monotonic() + seconds
        calls = 0
        while time.monotonic() < deadline:
            assert client.auth_service_get_user().id == "user-1"
            calls += 1
            time.sleep(0.02)
        results.put(("ok", calls))
    except BaseException as err:
        results.put(("error", repr(err)))
        raise


def take_a_token(results):
    webbrowser.open = _refuse_browser
    try:
        from lightning_sdk.lightning_cloud import cli_login

        results.put(("ok", cli_login.token()))
    except BaseException as err:
        results.put(("error", repr(err)))
        raise
