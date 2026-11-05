# This file is vendored.
# Do not edit it directly; changes will be overwritten.
# Make changes in the internal upstream repository instead.

import contextlib
import contextvars
import dataclasses
import enum
import os
import pathlib
from typing import Any, Callable, Dict, Iterator, Optional, Tuple

from lightning_sdk.lightning_cloud import cli_login, env
from lightning_sdk.lightning_cloud.login import Auth, AuthServer, Keys

_MISSING_CREDENTIALS = (
    "We couldn't find any credentials linked to your account. "
    "Please try logging in using the CLI command `lightning login`"
)
_LOGIN_FIRST = "No Lightning credentials are available. Run `lightning login` first."

_browser_login_allowed = contextvars.ContextVar(
    "lightning_browser_login_allowed", default=True
)


class CredentialKind(str, enum.Enum):
    TOKEN_FILE = "token_file"
    ENV_TOKEN = "env_token"
    LOGIN = "login"
    SESSION = "session"


REVOKE_FAILED = {
    CredentialKind.LOGIN: "The saved login could not be revoked on the server and may work until it expires.",
    CredentialKind.SESSION: "The saved session could not be revoked on the server and may work until it expires.",
}


@dataclasses.dataclass(frozen=True)
class Credential:
    kind: CredentialKind
    token: str = dataclasses.field(repr=False)

    @property
    def header(self) -> str:
        return f"Bearer {self.token}"


class LoginUnavailable(ValueError):
    """A login option the interim login can't honour."""


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


def _from_token_file() -> Optional[str]:
    path = os.environ.get(env.LIGHTNING_AUTH_TOKEN_FILE)
    if not path:
        return None
    try:
        raw = pathlib.Path(path).read_text()
    except FileNotFoundError:
        return None
    except OSError as err:
        raise cli_login.LoginError(
            f"{env.LIGHTNING_AUTH_TOKEN_FILE} names {path}, which can't be read "
            f"({err.strerror or err}). Fix the file or unset {env.LIGHTNING_AUTH_TOKEN_FILE}."
        ) from err
    return _present(raw)


def _from_env_token() -> Optional[str]:
    return _present(os.environ.get(Keys.AUTH_TOKEN.value))


# The order is the precedence.
_READERS = (
    (CredentialKind.TOKEN_FILE, _from_token_file),
    (CredentialKind.ENV_TOKEN, _from_env_token),
    (CredentialKind.LOGIN, cli_login._request_token),
    (CredentialKind.SESSION, cli_login._saved_session),
)


def _login_through_auth() -> None:
    # An SDK CLI may turn browser login off by patching Auth.authenticate, so
    # the source's own login goes through it rather than calling start_login.
    Auth().authenticate()


class CredentialSource:
    """Works out the credential each request sends, when it is sent."""

    def __init__(self, login: Optional[Callable[[], object]] = None) -> None:
        self._login = login or _login_through_auth
        # None until the source has tried its one login, then what to say
        # when a request still finds no credential.
        self._refusal: Optional[str] = None

    def resolve(self) -> Optional[Credential]:
        """The credential a request would send now. Never opens a browser."""
        for kind, read in _READERS:
            token = read()
            if not token:
                continue
            return Credential(kind, token)
        return None

    def header(self) -> str:
        """The authorization header for a request, logging in once when nothing is saved."""
        credential = self._resolve()
        if credential is None and self._refusal is None:
            if not _browser_login_allowed.get():
                raise ValueError(_LOGIN_FIRST)
            self._refusal = _MISSING_CREDENTIALS
            try:
                self._login()
            except ValueError as err:
                self._refusal = str(err)
                raise
            credential = self._resolve()
        if credential is None:
            raise ValueError(self._refusal)
        return credential.header

    def refresh(self, sent: str) -> bool:
        """Whether the request that sent ``sent`` should be retried.

        ``sent`` is the Authorization value (``Bearer <token>``), or a bare token,
        which counts as ``Bearer <token>``. True when a different credential is
        now available, or when the login refreshed the token it sent.
        """
        header = sent if sent.startswith("Bearer ") else f"Bearer {sent}"
        current = self._resolve()
        if current is None:
            return False
        if current.header != header:
            return True
        if current.kind is not CredentialKind.LOGIN:
            return False
        token = current.token
        fresh = self._noting_refusal(lambda: cli_login._request_token(token))
        return fresh is not None and fresh != token

    def _resolve(self) -> Optional[Credential]:
        return self._noting_refusal(self.resolve)

    def _noting_refusal(self, read: Callable[[], Any]) -> Any:
        try:
            return read()
        except cli_login.LoginError:
            # Every process sharing a refused login would otherwise open a
            # browser. Saying "run `lightning login`" once is enough.
            self._refusal = _MISSING_CREDENTIALS
            raise


def start_login(
    no_browser: bool = False,
    insecure_storage: bool = False,
    sign_in_params: Optional[Dict[str, str]] = None,
) -> Optional[cli_login.Login]:
    """Log in with the login ``LIGHTNING_CLI_OIDC_LOGIN`` selects when this is called.

    The new login returns the ``Login`` and ignores ``sign_in_params``. The
    interim login returns None, and raises ``LoginUnavailable`` for any other
    option, because it has no way to honour one.
    """
    if cli_login.oidc_login_enabled():
        return cli_login.login(
            no_browser=no_browser,
            insecure_storage=insecure_storage,
        )
    unavailable = [
        flag
        for flag, given in (
            ("--no-browser", no_browser),
            ("--insecure-storage", insecure_storage),
        )
        if given
    ]
    if unavailable:
        raise LoginUnavailable(
            f"{', '.join(unavailable)} needs the new login. "
            f"Set {cli_login.OIDC_LOGIN_ENV}=1 to use it."
        )
    AuthServer(sign_in_params).login_with_browser(Auth())
    return None


def logout() -> Tuple[CredentialKind, ...]:
    """Forget every saved login on this machine and revoke each on the server.

    Returns the kinds whose revoke failed, which may still work until they expire.
    """
    with cli_login._locked():
        origin = cli_login._origin()
        metadata = cli_login._read_metadata()
        login = cli_login._load(origin, cached=False)
        session = cli_login._saved_session()
        saved_here = isinstance(metadata, dict) and metadata.get("url") == origin
        if saved_here:
            cli_login._forget()
        Auth.secrets_file.unlink(missing_ok=True)
    failed = []
    if saved_here and (login is None or not cli_login._revoke(login.refresh_token)):
        failed.append(CredentialKind.LOGIN)
    if session is not None and not cli_login._revoke_session(session):
        failed.append(CredentialKind.SESSION)
    return tuple(failed)
