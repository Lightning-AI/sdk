# This file is vendored.
# Do not edit it directly; changes will be overwritten.
# Make changes in the internal upstream repository instead.

from enum import Enum
import hmac
import json
import logging
import os
import pathlib
import secrets
from dataclasses import dataclass
from typing import Dict, Optional, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import webbrowser

import requests

from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.openapi import ApiClient, Configuration
from lightning_sdk.lightning_cloud.openapi.api import \
    AuthServiceApi
from lightning_sdk.lightning_cloud.openapi.models.v1_token_login_request import \
    V1TokenLoginRequest
from lightning_sdk.lightning_cloud.openapi.models.v1_refresh_request import \
    V1RefreshRequest

logger = logging.getLogger(__name__)

# Authentication override types
AuthOverride = Literal["auth_token"]

class Keys(Enum):
    # USERNAME = "LIGHTNING_USERNAME"
    USER_ID = "LIGHTNING_USER_ID"
    AUTH_TOKEN = "LIGHTNING_AUTH_TOKEN"

    @property
    def suffix(self):
        return self.value.lstrip("LIGHTNING_").lower()


@dataclass
class Auth:
    # username: Optional[str] = None
    user_id: Optional[str] = None
    auth_token: Optional[str] = None

    secrets_file = pathlib.Path(env.LIGHTNING_CREDENTIAL_PATH)

    def __post_init__(self):
        for key in Keys:
            # Only set from environment if not already set
            if getattr(self, key.suffix) is None:
                setattr(self, key.suffix, os.environ.get(key.value, None))

    def load(self) -> bool:
        """Load credentials from disk and update properties with credentials.

        Returns
        ----------
        True if credentials are available.
        """
        if not self.secrets_file.exists():
            logger.debug("Credentials file not found.")
            return False
        with self.secrets_file.open() as creds:
            credentials = json.load(creds)
            for key in Keys:
                setattr(self, key.suffix, credentials.get(key.suffix, None))
            return True

    def save(
        self,
        user_id: str = "",
        auth_token: str = "",
        # username: str = "",
    ) -> None:
        """Replace the saved login."""
        stored = {
            Keys.USER_ID.suffix: user_id,
            Keys.AUTH_TOKEN.suffix: auth_token,
        }

        self.secrets_file.parent.mkdir(exist_ok=True, parents=True)
        payload = json.dumps(stored).encode()
        fd = os.open(self.secrets_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        # os.open's mode applies only to a new file, so an existing one needs chmod.
        os.chmod(self.secrets_file, 0o600)

        for key in Keys:
            setattr(self, key.suffix, stored.get(key.suffix))
        logger.debug("credentials saved successfully")

    @classmethod
    def clear(cls) -> None:
        """remove credentials from disk and env variables."""
        if cls.secrets_file.exists():
            cls.secrets_file.unlink()
        for key in Keys:
            os.environ.pop(key.value, None)
        logger.debug("credentials removed successfully")

    def get_auth_header(self, override: Optional[AuthOverride] = None) -> Optional[str]:
        """Get an authorization header, with an optional override.

        By default, returns the credential every request would send: the file
        named by ``LIGHTNING_AUTH_TOKEN_FILE``, then ``LIGHTNING_AUTH_TOKEN``,
        then the service-account key in ``LIGHTNING_API_KEY``, then the saved
        login, then the interim session. This never opens a browser.

        Parameters
        ----------
        override : AuthOverride, optional
            Use a token held by this instance instead:
            - "auth_token": this instance's auth token, as Bearer
            - None: the credential every request would send (default)

        Returns
        -------
        Optional[str]
            The authorization header for the specified method.

        Raises
        ------
        ValueError
            If the specified override is not available or invalid.
        """
        if override == "auth_token":
            if not self.auth_token:
                raise ValueError(
                    "Auth token override requested but no JWT token available. "
                    "Please use token_login() method first."
                )
            return f"Bearer {self.auth_token}"

        elif override is None:
            from lightning_sdk.lightning_cloud.credentials import CredentialSource, browser_login

            with browser_login(False):
                return CredentialSource().header()

        else:
            raise ValueError(f"Invalid authentication override: {override}")

    @property
    def auth_header(self) -> Optional[str]:
        """The credential every request would send, without opening a browser."""
        return self.get_auth_header()

    def _run_server(self) -> None:
        """Start the login ``LIGHTNING_CLI_OIDC_LOGIN`` selects."""
        from lightning_sdk.lightning_cloud.credentials import start_login

        start_login()

    def authenticate(self) -> Optional[str]:
        """Performs end to end authentication flow.

        Returns
        ----------
        authorization header to use when authentication completes. With no
        credential, this logs in through ``_run_server``, unless browser login
        is turned off.
        """
        from lightning_sdk.lightning_cloud.credentials import CredentialSource

        return CredentialSource(login=self._run_server).header()

    def token_login(self, token_key: str, save_token: bool = True) -> Optional[str]:
        """Performs token-based authentication.
        
        This method sends a request to the token login endpoint to authenticate
        using an auth token key, optionally saves the returned JWT token, and 
        returns the authorization header.
        
        Parameters
        ----------
        token_key : str
            The auth token key to use for authentication.
        save_token : bool, optional
            Whether to save the JWT token for future use. Defaults to True.
            If False, the token is only used for the current session.
            
        Returns
        -------
        Optional[str]
            The authorization header to use for subsequent requests.
            
        Raises
        ------
        RuntimeError
            If the token login request fails.
        ValueError
            If the response from the server is invalid.
        """
        config = Configuration()
        config.host = env.LIGHTNING_CLOUD_URL
        api_client = ApiClient(configuration=config)
        api_client.user_agent = env.USER_AGENT
        auth_api = AuthServiceApi(api_client)

        logger.debug(f"Attempting token login to {config.host}")

        try:
            body = V1TokenLoginRequest(token_key=token_key)
            response = auth_api.auth_service_token_login(body)

        except requests.RequestException as e:
            logger.error(f"Token login request failed: {e}")
            raise RuntimeError(
                "Failed to connect to the token login endpoint. "
                "Please check your network connection and the server status."
            ) from e

        # Extract the JWT token from the response
        jwt_token = getattr(response, "token", None)

        if not jwt_token:
            logger.error(
                f"No token received from token login response: {response}"
            )
            raise ValueError(
                "The token login response did not contain a valid JWT token."
            )

        # Set the JWT token in memory
        self.auth_token = jwt_token
        
        # Optionally save the JWT token to disk
        if save_token:
            self.save(auth_token=jwt_token)
            logger.info("Successfully authenticated using auth token and saved to disk.")
        else:
            logger.info("Successfully authenticated using auth token (not saved to disk).")

        return f"Bearer {jwt_token}"

    def refresh_token(self, duration: int = 43200) -> Optional[str]:
        """Refreshes the current JWT token.
        
        This method sends a request to the refresh endpoint to get a new JWT token
        with the specified duration, saves the new token, and returns the updated
        authorization header.
        
        Parameters
        ----------
        duration : int, optional
            Duration in seconds for the new token. Can range from 900 seconds (15 minutes)
            up to a maximum of 129,600 seconds (36 hours), with a default of 43,200 seconds (12 hours).
            
        Returns
        -------
        Optional[str]
            The updated authorization header with the new JWT token.
            
        Raises
        ------
        RuntimeError
            If the refresh request fails.
        ValueError
            If no valid JWT token is available to refresh, or if the response is invalid.
        """
        if not self.auth_token:
            raise ValueError(
                "No JWT token available to refresh. Please authenticate first using "
                "token_login() or authenticate() methods."
            )
        
        config = Configuration()
        config.host = env.LIGHTNING_CLOUD_URL
        # Set the current auth token as the authorization header
        config.api_key_prefix['Authorization'] = 'Bearer'
        config.api_key['Authorization'] = self.auth_token
        
        api_client = ApiClient(configuration=config)
        api_client.user_agent = env.USER_AGENT
        auth_api = AuthServiceApi(api_client)

        logger.debug(f"Attempting to refresh JWT token with duration {duration} seconds")

        try:
            body = V1RefreshRequest(duration=str(duration))
            response = auth_api.auth_service_refresh(body)

        except requests.RequestException as e:
            logger.error(f"Token refresh request failed: {e}")
            raise RuntimeError(
                "Failed to connect to the refresh endpoint. "
                "Please check your network connection and the server status."
            ) from e

        # Extract the new JWT token from the response
        new_jwt_token = getattr(response, "token", None)

        if not new_jwt_token:
            logger.error(
                f"No token received from refresh response: {response}"
            )
            raise ValueError(
                "The refresh response did not contain a valid JWT token."
            )

        # Save the new JWT token
        self.save(auth_token=new_jwt_token)
        logger.info("Successfully refreshed JWT token.")

        return f"Bearer {new_jwt_token}"

    def create_api_client(self, override: Optional[AuthOverride] = None) -> 'ApiClient':
        """Create an API client with optional authentication override.
        
        This is a convenience method for creating API clients that use a specific
        authentication method instead of the default automatic selection.
        
        Parameters
        ----------
        override : AuthOverride, optional
            Override the default authentication method for this API client.
            See get_auth_header() for available options.
            
        Returns
        -------
        ApiClient
            Configured API client with the specified authentication method.
        """
        from lightning_sdk.lightning_cloud.openapi import ApiClient, Configuration
        
        config = Configuration()
        config.host = env.LIGHTNING_CLOUD_URL
        
        # Get the auth header for the specified override
        auth_header = self.get_auth_header(override)
        
        # Create the API client
        client = ApiClient(configuration=config)
        client.user_agent = env.USER_AGENT
        
        # Set the Authorization header directly in default_headers
        if auth_header:
            client.set_default_header('Authorization', auth_header)
        
        return client


_INTERIM_TIMED_OUT = (
    "The browser didn't finish the login within 5 minutes, so nothing was saved. "
    "Run `lightning login` again."
)


class AuthServer:
    """The interim browser login, which saves a ``sess_`` token as ``auth_token``."""

    def __init__(self, sign_in_params: Optional[Dict[str, str]] = None) -> None:
        self.sign_in_params = dict(sign_in_params or {})

    def get_auth_url(self, port: int) -> str:
        redirect_uri = f"http://localhost:{port}/login-complete"
        params = urlencode(dict(redirectTo=redirect_uri, **self.sign_in_params))
        return f"{env.LIGHTNING_CLOUD_URL}/sign-in?{params}"

    def login_with_browser(self, auth: Auth) -> None:
        from lightning_sdk.lightning_cloud import cli_login

        state = secrets.token_urlsafe(32)

        def complete(query: Dict[str, str]) -> None:
            if not hmac.compare_digest(query.get("state", "").encode(), state.encode()):
                raise cli_login.LoginError(
                    "The login callback didn't match this login, so nothing was saved. "
                    "Run `lightning login` again."
                )
            token = query.get("token", "")
            if not token:
                raise cli_login.LoginError(
                    "The sign-in page sent no token, so nothing was saved. "
                    "Run `lightning login` again, or update the SDK."
                )

            def save() -> str:
                auth.save(auth_token=token, user_id=query.get("userID", ""))
                cli_login._forget()
                return token

            cli_login._replace_saved(save)
            logger.info("Authentication Successful")

        with cli_login._callback_server("/login-complete", complete, _INTERIM_TIMED_OUT) as (port, wait):
            redirect_uri = f"http://localhost:{port}/login-complete"
            url = _with_state(self.get_auth_url(port), redirect_uri, state)
            try:
                requests.head(
                    url,
                    headers={"User-Agent": env.USER_AGENT},
                    timeout=env.LIGHTNING_CLOUD_CONNECT_TIMEOUT,
                    verify=env.SSL_CA_CERT,
                )
            except requests.RequestException as err:
                raise cli_login.LoginError(
                    f"Couldn't reach {env.LIGHTNING_CLOUD_URL}. Check your connection and try again."
                ) from err
            logger.info(f"login started for lightning.ai, opening {url}")
            if not webbrowser.open(url):
                if os.environ.get("LIGHTNING_DEPLOYMENT_ID"):
                    raise cli_login.LoginError(cli_login._DEPLOYMENT)
                raise cli_login.LoginError(
                    "No browser could be opened to log in. Run `lightning login` where a "
                    "browser is available, or set LIGHTNING_AUTH_TOKEN."
                )
            wait()


def _with_state(url: str, redirect_uri: str, state: str) -> str:
    # A subclass may build its own URL from get_auth_url(port), which knows no
    # state, so the state goes onto whichever redirectTo names this callback.
    parts = urlsplit(url)
    stateful = f"{redirect_uri}?{urlencode(dict(state=state))}"
    query = [
        (key, stateful if key == "redirectTo" and value == redirect_uri else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit(parts._replace(query=urlencode(query)))
