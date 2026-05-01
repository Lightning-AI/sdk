import base64
from enum import Enum
import json
import logging
import os
import pathlib
from dataclasses import dataclass
from typing import Optional, Literal
from urllib.parse import urlencode

import webbrowser

import requests
import uvicorn
from fastapi import FastAPI, Query, Request
from starlette.background import BackgroundTask
from starlette.responses import RedirectResponse

from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.openapi import ApiClient, Configuration
from lightning_sdk.lightning_cloud.openapi.api import \
    AuthServiceApi
from lightning_sdk.lightning_cloud.openapi.models.v1_guest_login_request import \
    V1GuestLoginRequest
from lightning_sdk.lightning_cloud.openapi.models.v1_token_login_request import \
    V1TokenLoginRequest
from lightning_sdk.lightning_cloud.openapi.models.v1_refresh_request import \
    V1RefreshRequest

logger = logging.getLogger(__name__)

# Authentication override types
AuthOverride = Literal["auth_token", "api_key", "guest"]

class Keys(Enum):
    # USERNAME = "LIGHTNING_USERNAME"
    USER_ID = "LIGHTNING_USER_ID"
    API_KEY = "LIGHTNING_API_KEY"
    AUTH_TOKEN = "LIGHTNING_AUTH_TOKEN"

    @property
    def suffix(self):
        return self.value.lstrip("LIGHTNING_").lower()


@dataclass
class Auth:
    # username: Optional[str] = None
    user_id: Optional[str] = None
    api_key: Optional[str] = None
    auth_token: Optional[str] = None

    secrets_file = pathlib.Path(env.LIGHTNING_CREDENTIAL_PATH)

    def __post_init__(self):
        for key in Keys:
            # Only set from environment if not already set
            if getattr(self, key.suffix) is None:
                setattr(self, key.suffix, os.environ.get(key.value, None))

        # used by authenticate method
        self._with_env_var = bool(self.api_key or self.auth_token)

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

    def save(self,
             token: str = "",
             user_id: str = "",
             api_key: str = "",
             auth_token: str = "",
             # username: str = "",
        ) -> None:
        """save credentials to disk."""
        self.secrets_file.parent.mkdir(exist_ok=True, parents=True)
        with self.secrets_file.open("w") as f:
            json.dump(
                {
                    # f"{Keys.USERNAME.suffix}": username,
                    f"{Keys.USER_ID.suffix}": user_id,
                    f"{Keys.API_KEY.suffix}": api_key,
                    f"{Keys.AUTH_TOKEN.suffix}": auth_token,
                },
                f,
            )

        # self.username = username
        self.user_id = user_id
        self.api_key = api_key
        self.auth_token = auth_token
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
        """Get authentication header with optional override.
        
        By default, uses the automatic priority selection (auth_token > api_key).
        You can override this for specific cases where you need a different auth method.
        
        Parameters
        ----------
        override : AuthOverride, optional
            Override the default authentication method:
            - "auth_token": Force use of JWT auth token (Bearer)
            - "api_key": Force use of API key (Basic)
            - "guest": Force use of guest credentials (Basic)
            - None: Use automatic selection (default)
            
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
        
        elif override == "api_key":
            if not self.api_key or not self.user_id:
                raise ValueError(
                    "API key override requested but no API key or user ID available. "
                    "Please set LIGHTNING_API_KEY and LIGHTNING_USER_ID environment variables "
                    "or use authenticate() method."
                )
            token = f"{self.user_id}:{self.api_key}"
            return f"Basic {base64.b64encode(token.encode('ascii')).decode('ascii')}"  # noqa E501
        
        elif override == "guest":
            if not self.api_key or not self.user_id:
                raise ValueError(
                    "Guest override requested but no guest credentials available. "
                    "Please call guest_login() method first."
                )
            token = f"{self.user_id}:{self.api_key}"
            return f"Basic {base64.b64encode(token.encode('ascii')).decode('ascii')}"  # noqa E501
        
        elif override is None:
            # Use the original automatic selection logic (default behavior)
            if self.auth_token:
                return f"Bearer {self.auth_token}"
            elif self.api_key:
                token = f"{self.user_id}:{self.api_key}"
                return f"Basic {base64.b64encode(token.encode('ascii')).decode('ascii')}"  # noqa E501
            else:
                raise ValueError(
                    "No authentication credentials available. Please authenticate first using "
                    "token_login(), guest_login(), or authenticate() methods."
                )
        
        else:
            raise ValueError(f"Invalid authentication override: {override}")

    @property
    def auth_header(self) -> Optional[str]:
        """authentication header used by lightning-cloud client (automatic selection)."""
        return self.get_auth_header()

    def _run_server(self) -> None:
        """start a server to complete authentication."""
        AuthServer().login_with_browser(self)

    def authenticate(self) -> Optional[str]:
        """Performs end to end authentication flow.

        Returns
        ----------
        authorization header to use when authentication completes.
        """
        if self._with_env_var:
            logger.debug("successfully loaded credentials from env")
            return self.auth_header

        if not self.load():
            logger.debug(
                "failed to load credentials, opening browser to get new.")
            self._run_server()
            return self.auth_header

        elif self.auth_token:
            return self.auth_header
        elif self.user_id and self.api_key:
            return self.auth_header

        raise ValueError(
            "We couldn't find any credentials linked to your account. Please try logging in using the CLI command `lightning login`"
        )

    def guest_login(self) -> Optional[str]:
        """Performs guest user authentication.
        This method sends a request to the guest login endpoint to get temporary
        credentials, saves them, and returns the authorization header.
        Useful to log experiments as a non signed in user, using a guest account
        in the background.
        Returns
        -------
        Optional[str]
            The authorization header to use for subsequent requests.
        Raises
        ------
        RuntimeError
            If the guest login request fails.
        ValueError
            If the response from the server is invalid.
        """

        config = Configuration()
        config.host = env.LIGHTNING_CLOUD_URL
        api_client = ApiClient(configuration=config)
        auth_api = AuthServiceApi(api_client)

        logger.debug(f"Attempting guest login to {config.host}")

        try:
            # The body is an empty object for a guest login.
            body = V1GuestLoginRequest()
            credentials = auth_api.auth_service_guest_login(body)

        except requests.RequestException as e:
            logger.error(f"Guest login request failed: {e}")
            raise RuntimeError(
                "Failed to connect to the guest login endpoint. "
                "Please check your network connection and the server status."
            ) from e

        # attributes based on the `V1GuestLoginResponse` model.
        user = getattr(credentials, "user", None)
        user_id = getattr(user, "id", None) if user else None
        api_key = getattr(user, "api_key", None) if user else None

        if not all([user_id, api_key]):
            logger.error(
                f"Incomplete credentials received from guest login: {credentials}"
            )
            raise ValueError(
                "The guest login response did not contain the required 'user_id' and 'api_key' fields."
            )

        self.save(user_id=user_id, api_key=api_key)
        logger.info("Successfully authenticated as a guest user.")

        return self.authenticate()

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

        return self.auth_header

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

        return self.auth_header

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
        
        # Set the Authorization header directly in default_headers
        if auth_header:
            client.set_default_header('Authorization', auth_header)
        
        return client


class AuthServer:

    def get_auth_url(self, port: int) -> str:
        redirect_uri = f"http://localhost:{port}/login-complete"
        params = urlencode(dict(redirectTo=redirect_uri))
        return f"{env.LIGHTNING_CLOUD_URL}/sign-in?{params}"

    def login_with_browser(self, auth: Auth) -> None:
        from lightning_sdk.lightning_cloud.utils.network import find_free_network_port

        app = FastAPI()
        port = find_free_network_port()
        url = self.get_auth_url(port)
        try:
            # check if server is reachable or catch any network errors
            requests.head(url)
        except requests.ConnectionError as e:
            raise requests.ConnectionError(
                f"No internet connection available. Please connect to a stable internet connection \n{e}"  # noqa E501
            )
        except requests.RequestException as e:
            raise requests.RequestException(
                f"An error occurred with the request. Please report this issue to Lightning Team \n{e}"  # noqa E501
            )

        logger.info(f"login started for lightning.ai, opening {url}")
        ok = webbrowser.open(url)
        if not ok:
            # can't open a browser, authentication failed
            deployment_id = os.environ.get("LIGHTNING_DEPLOYMENT_ID", None)
            if deployment_id is not None and deployment_id != "":
                raise RuntimeError("Failed to authenticate to Lightning. Ensure that you have selected 'Include SDK credentials' in the 'Environment' section of the deployment settings.")
            raise RuntimeError("Failed to authenticate to Lightning. When running without access to a browser, 'LIGHTNING_USER_ID' and 'LIGHTNING_API_KEY' should be exported.")

        @app.get("/login-complete")
        async def save_token(request: Request,
                             token="",
                             key="",
                             user_id: str = Query("", alias="userID")):
            if token:
                auth.save(token=token,
                          # username=user_id,
                          user_id=user_id,
                          api_key=key)
                logger.info("Authentication Successful")
            else:
                logger.warning(
                    "Authentication Failed. This is most likely because you're using an older version of the CLI. \n"  # noqa E501
                    "Please try to update the CLI or open an issue with this information \n"  # noqa E501
                    f"expected token in {request.query_params.items()}")

            # Include the credentials in the redirect so that UI will also be logged in
            params = urlencode(dict(token=token, key=key, userID=user_id))

            return RedirectResponse(
                url=f"{env.LIGHTNING_CLOUD_URL}/me/apps?{params}",
                # The response background task is being executed right after the server finished writing the response
                background=BackgroundTask(stop_server))

        def stop_server():
            server.should_exit = True

        server = uvicorn.Server(
            config=uvicorn.Config(app, port=port, log_level="error"))
        server.run()
