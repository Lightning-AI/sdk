"""Non-interactive authentication helpers for CLI commands."""

import base64
import hashlib
import hmac
import json
import os
import secrets
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from pathlib import Path
from typing import Generator, Optional, Tuple
from urllib.parse import urlencode

import requests
import rich_click as click

from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.login import Auth, AuthServer, logger

_BROWSER_AUTH_ALLOWED = ContextVar("lightning_browser_auth_allowed", default=True)
_ORIGINAL_AUTH_SAVE = Auth.save

_CLIENT_ID = "lightning-cli"
_PASTE_ATTEMPTS = 3


def _generate_state() -> str:
    return base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode("ascii")


def _pkce_pair() -> Tuple[str, str]:
    """Return a PKCE `(verifier, S256 challenge)` pair."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=")
    return verifier, challenge.decode("ascii")


def _authorize_url(redirect_uri: str, state: str, challenge: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": _CLIENT_ID,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{env.LIGHTNING_CLOUD_URL}/oidc/authorize?{query}"


class _CodeRejectedError(Exception):
    """The token endpoint refused the code; `str(e)` is its OAuth error."""


def _exchange_code(code: str, verifier: str, redirect_uri: str) -> str:
    """Trade an approved code and its PKCE verifier for a CLI session token."""
    try:
        response = requests.post(
            f"{env.LIGHTNING_CLOUD_URL}/oidc/token",
            data={
                "grant_type": "authorization_code",
                "client_id": _CLIENT_ID,
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": redirect_uri,
            },
            timeout=10,
        )
    except requests.ConnectionError as e:
        raise ConnectionError(str(e)) from e
    body = _json_body(response)
    if response.ok and body.get("access_token"):
        return body["access_token"]
    raise _CodeRejectedError(body.get("error") or f"HTTP {response.status_code}")


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
    """Sign in with an authorization code and PKCE, delivered to a callback on 127.0.0.1."""
    import webbrowser

    import uvicorn
    from fastapi import FastAPI
    from starlette.background import BackgroundTask
    from starlette.responses import RedirectResponse

    from lightning_sdk.lightning_cloud.utils.network import find_free_network_port

    expected_state = _generate_state()
    verifier, challenge = _pkce_pair()
    app = FastAPI()
    port = find_free_network_port()
    redirect_uri = f"http://127.0.0.1:{port}/callback"
    url = _authorize_url(redirect_uri, expected_state, challenge)

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
        if os.environ.get("LIGHTNING_DEPLOYMENT_ID"):
            raise RuntimeError(
                "Failed to authenticate to Lightning. Ensure that you have selected 'Include SDK credentials' in the "
                "'Environment' section of the deployment settings."
            )
        click.echo("No browser could be opened on this machine.")
        login_with_pasted_code(auth)
        return

    @app.get("/callback")
    def save_token(code: str = "", state: str = "", error: str = "") -> RedirectResponse:
        failure = ""
        if not state or not hmac.compare_digest(state, expected_state):
            failure = "state mismatch"
        elif error or not code:
            failure = error or "no code in the callback"
        else:
            try:
                auth.save(auth_token=_exchange_code(code, verifier, redirect_uri))
            except (_CodeRejectedError, ConnectionError) as e:
                failure = str(e)

        if failure:
            logger.warning(f"Authentication Failed ({failure}). Run `lightning login` again, or update the CLI.")
            target = f"{env.LIGHTNING_CLOUD_URL}/cli-login-failed"
        else:
            logger.info("Authentication Successful")
            target = f"{env.LIGHTNING_CLOUD_URL}/cli-login-successful"

        return RedirectResponse(
            url=target,
            background=BackgroundTask(stop_server),
        )

    def stop_server() -> None:
        server.should_exit = True

    server = uvicorn.Server(config=uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    server.run()


Auth.save = _save_with_session_token
AuthServer.login_with_browser = _login_with_browser


def login_with_pasted_code(auth: Auth) -> None:
    """Sign in on a machine without a browser: approve on any device, then paste the code shown there."""
    redirect_uri = f"{env.LIGHTNING_CLOUD_URL}/cli-login"
    verifier, challenge = _pkce_pair()
    click.echo(
        "To sign in, open this address in a browser on any device and approve the request:\n\n"
        f"    {_authorize_url(redirect_uri, _generate_state(), challenge)}\n\n"
        "The page then shows a code. Only paste a code from a page you opened this way; "
        "never give it to anyone, as it gives full access to your Lightning account."
    )
    for attempt in range(_PASTE_ATTEMPTS):
        code = click.prompt("Code").strip()
        try:
            auth.save(auth_token=_exchange_code(code, verifier, redirect_uri))
            return
        except _CodeRejectedError as e:
            if str(e) != "invalid_grant":
                raise RuntimeError(f"Login failed: {e}.") from None
            if attempt < _PASTE_ATTEMPTS - 1:
                click.echo("That code was not accepted. It works once and expires after a minute. Try again.")
    raise RuntimeError("Login failed: the code was not accepted. Run `lightning login --no-browser` again.")


def _json_body(response: requests.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


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
