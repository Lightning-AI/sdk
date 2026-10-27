"""Non-interactive authentication helpers for CLI commands."""

import base64
import hmac
import json
import os
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from pathlib import Path
from typing import Generator, Optional
from urllib.parse import urlencode

import requests
import rich_click as click

from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.login import Auth, AuthServer, logger

_BROWSER_AUTH_ALLOWED = ContextVar("lightning_browser_auth_allowed", default=True)
_ORIGINAL_AUTH_SAVE = Auth.save


def _generate_state() -> str:
    return base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode("ascii")


def _save_with_session_token(
    self: Auth,
    token: str = "",
    user_id: str = "",
    api_key: str = "",
    auth_token: str = "",
) -> None:
    """Persist session tokens (`token`) as `auth_token` so the SDK/CLI sends `Bearer sess_...`."""
    if not auth_token and token and (not api_key or token.startswith("sess_")):
        auth_token = token
        if token.startswith("sess_"):
            api_key = ""
    _ORIGINAL_AUTH_SAVE(
        self,
        token=token,
        user_id=user_id,
        api_key=api_key,
        auth_token=auth_token,
    )
    with suppress(OSError):
        os.chmod(self.secrets_file, 0o600)


def _login_with_browser(self: AuthServer, auth: Auth) -> None:
    """Complete browser authentication without forwarding credentials back to `/me/apps`."""
    import webbrowser

    import uvicorn
    from fastapi import FastAPI, Query
    from starlette.background import BackgroundTask
    from starlette.responses import RedirectResponse

    from lightning_sdk.lightning_cloud.utils.network import find_free_network_port

    expected_state = _generate_state()
    app = FastAPI()
    port = find_free_network_port()
    base_url = self.get_auth_url(port)
    redirect_uri = f"http://localhost:{port}/login-complete"
    if urlencode({"redirectTo": redirect_uri}) in base_url:
        stateful_redirect = f"{redirect_uri}?{urlencode({'state': expected_state})}"
        url = base_url.replace(urlencode({"redirectTo": redirect_uri}), urlencode({"redirectTo": stateful_redirect}), 1)
    else:
        url = base_url

    try:
        requests.head(url, timeout=10)
    except requests.ConnectionError as e:
        raise requests.ConnectionError(
            f"No internet connection available. Please connect to a stable internet connection \n{e}"
        ) from e
    except requests.RequestException as e:
        raise requests.RequestException(
            f"An error occurred with the request. Please report this issue to Lightning Team \n{e}"
        ) from e

    logger.info(f"login started for lightning.ai, opening {url}")
    if not webbrowser.open(url):
        deployment_id = os.environ.get("LIGHTNING_DEPLOYMENT_ID")
        if deployment_id:
            raise RuntimeError(
                "Failed to authenticate to Lightning. Ensure that you have selected 'Include SDK credentials' in the "
                "'Environment' section of the deployment settings."
            )
        raise RuntimeError(
            "Failed to authenticate to Lightning. When running without access to a browser, "
            "'LIGHTNING_API_KEY' should be exported."
        )

    @app.get("/login-complete")
    async def save_token(
        token: str = "",
        key: str = "",
        state: str = "",
        user_id: str = Query("", alias="userID"),
    ) -> RedirectResponse:
        state_valid = bool(state) and hmac.compare_digest(state, expected_state)
        if token and state_valid:
            auth.save(token=token, user_id=user_id, api_key=key)
            logger.info("Authentication Successful")
            target = f"{env.LIGHTNING_CLOUD_URL}/cli-login-successful"
        else:
            reason = "no token in the callback" if not token else "state mismatch"
            logger.warning(
                f"Authentication Failed ({reason}). If the browser was already signed in, the sign-in page "
                "could not mint a CLI token. Run `lightning login` again, or update the CLI."
            )
            target = f"{env.LIGHTNING_CLOUD_URL}/cli-login-failed"

        return RedirectResponse(
            url=target,
            background=BackgroundTask(stop_server),
        )

    def stop_server() -> None:
        server.should_exit = True

    server = uvicorn.Server(config=uvicorn.Config(app, port=port, log_level="error"))
    server.run()


Auth.save = _save_with_session_token
AuthServer.login_with_browser = _login_with_browser


def logout_session(auth: Auth) -> None:
    """Revoke the active CLI session token on the server and clear local credentials."""
    token = getattr(auth, "auth_token", None)
    if not isinstance(token, str) or not token:
        secrets_file = getattr(auth, "secrets_file", None)
        if isinstance(secrets_file, Path) and secrets_file.exists():
            try:
                with secrets_file.open() as creds:
                    data = json.load(creds)
                loaded = data.get("auth_token")
                if isinstance(loaded, str) and loaded:
                    token = loaded
            except Exception:
                token = None
    if isinstance(token, str) and token:
        with suppress(requests.RequestException):
            requests.post(
                f"{env.LIGHTNING_CLOUD_URL}/v1/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
    auth.clear()


@contextmanager
def browser_authentication(allowed: bool) -> Generator[None, None, None]:
    """Temporarily control whether missing credentials may start browser authentication."""
    token = _BROWSER_AUTH_ALLOWED.set(allowed)
    authenticate = Auth.authenticate

    def guarded_authenticate(auth: Auth) -> Optional[str]:
        if _BROWSER_AUTH_ALLOWED.get():
            return authenticate(auth)

        has_own_run_server = "_run_server" in auth.__dict__
        run_server = auth.__dict__.get("_run_server")

        def blocked_run_server() -> None:
            raise ValueError("No Lightning credentials are available. Run `lightning login` first.")

        auth.__dict__["_run_server"] = blocked_run_server
        try:
            return authenticate(auth)
        finally:
            if has_own_run_server:
                auth.__dict__["_run_server"] = run_server
            else:
                auth.__dict__.pop("_run_server", None)

    Auth.authenticate = guarded_authenticate
    try:
        yield
    finally:
        Auth.authenticate = authenticate
        _BROWSER_AUTH_ALLOWED.reset(token)


def require_auth_header() -> str:
    """Return available credentials without falling back to browser authentication."""
    auth = Auth()
    try:
        header = auth.auth_header
    except ValueError:
        header = None

    if header:
        return header

    if auth.load():
        try:
            header = auth.auth_header
        except ValueError:
            header = None
        if header:
            return header

    raise click.UsageError("No Lightning credentials are available. Run `lightning login` first.")
