# This file is vendored.
# Do not edit it directly; changes will be overwritten.
# Make changes in the internal upstream repository instead.

import contextlib
import contextvars
import os
import pathlib
from typing import Iterator, Optional

from lightning_sdk.lightning_cloud import cli_login, env
from lightning_sdk.lightning_cloud.login import Auth, Keys

_MISSING_CREDENTIALS = (
    "We couldn't find any credentials linked to your account. "
    "Please try logging in using the CLI command `lightning login`"
)
_LOGIN_FIRST = "No Lightning credentials are available. Run `lightning login` first."

_browser_login_allowed = contextvars.ContextVar(
    "lightning_browser_login_allowed", default=True
)


@contextlib.contextmanager
def browser_login(allowed: bool) -> Iterator[None]:
    """Allow or forbid opening a browser to log in when no credential is found."""
    token = _browser_login_allowed.set(allowed)
    try:
        yield
    finally:
        _browser_login_allowed.reset(token)


def _present(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    if text == "":
        return None
    return text


class CredentialSource:
    def __init__(self) -> None:
        self._may_open_browser = True
        self._login_token: Optional[str] = None

    def header(self) -> str:
        token = self._token()
        if token is None and self._may_open_browser:
            if not _browser_login_allowed.get():
                raise ValueError(_LOGIN_FIRST)
            self._may_open_browser = False
            Auth()._run_server()
            token = self._token()
        if not token:
            raise ValueError(_MISSING_CREDENTIALS)
        return f"Bearer {token}"

    def refresh(self) -> bool:
        """Refresh the login after the server refused its access token.

        Only the saved login can refresh, and only when its token was the one
        last handed out.
        """
        rejected = self._login_token
        if rejected is None:
            return False
        fresh = self._saved_login_token(rejected)
        return fresh is not None and fresh != rejected

    def _token(self) -> Optional[str]:
        self._login_token = None
        for read in (
            self._from_token_file,
            self._from_env_token,
            self._from_saved_login,
        ):
            token = read()
            if token:
                return token
        return None

    def _from_token_file(self) -> Optional[str]:
        path = os.environ.get(env.LIGHTNING_AUTH_TOKEN_FILE)
        if not path:
            return None
        try:
            raw = pathlib.Path(path).read_text()
        except FileNotFoundError:
            return None
        return _present(raw)

    def _from_env_token(self) -> Optional[str]:
        return _present(os.environ.get(Keys.AUTH_TOKEN.value))

    def _from_saved_login(self) -> Optional[str]:
        self._login_token = self._saved_login_token()
        if self._login_token:
            return self._login_token
        auth = Auth()
        if not auth.load():
            return None
        token = _present(auth.auth_token)
        if token:
            return token
        return _present(auth.api_key)

    def _saved_login_token(self, rejected: Optional[str] = None) -> Optional[str]:
        try:
            return cli_login._request_token(rejected)
        except cli_login.LoginError:
            # Every process sharing a refused login would otherwise open a
            # browser. Saying "run `lightning login`" once is enough.
            self._may_open_browser = False
            raise
