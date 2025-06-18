import importlib
import json
import os
import socket
import threading
from contextlib import suppress
from functools import partial
from importlib import metadata
from pathlib import Path
from typing import Optional, Tuple

from lightning_sdk.api.license_api import LICENSE_SIGNING_URL, LicenseApi, generate_url_user_settings
from lightning_sdk.lightning_cloud.login import Auth

MESSAGE_NOT_AUTHENTICATED = (
    "┌─────────────────────────────────────────────────────────────────────────┐\n"
    "│ ⚠️  No authenticated user found or license API is not available.        │\n"
    "│                                                                         │\n"
    "│   Please make sure you are logged in and have a valid license.          │\n"
    "│   If you're not logged in, you can use the following command:           │\n"
    "│                                                                         │\n"
    "│     lightning login                                                     │\n"
    "└─────────────────────────────────────────────────────────────────────────┘"
)
MESSAGE_AUTH_NO_LICENSE = (
    "┌──────────────────────────────────────────────────────────────────────────────────────────────┐\n"
    "│ ⚠️ No valid license found for the authenticated user for product '{self.product_name}'.      │\n"
    "│                                                                                              │\n"
    "│   Please ensure you have an approved license for this product.                               │\n"
    "│   If you believe this is an error, please contact support.                                   │\n"
    "│                                                                                              │\n"
    "│   You can review or update your license settings here:                                       │\n"
    f"│     {LICENSE_SIGNING_URL:<89}│\n"
    "└──────────────────────────────────────────────────────────────────────────────────────────────┘"
)
MESSAGE_GUIDE_SIGN_LICENSE = (
    "┌───────────────────────────────────────────────────────────────────────────────────────────────────────────┐\n"
    "│ ⚠️ {reason} │\n"
    "│ Details: license key ({license_strats}...{license_ends}) for package {package_name:<56} │\n"
    "│ Please make sure you have signed the license agreement and set the license key.                           │\n"
    "│                                                                                                           │\n"
    "│ Sign the license agreement here (if you dont have Lightning account, you will asked to create one):       │\n"
    "│   {link}\n"
    "│                                                                                                           │\n"
    "│ Once you have the license key, you may need to reinstall this package to activate it. Use the commands:   │\n"
    "│                                                                                                           │\n"
    "│   export LIGHTNING_LICENSE_KEY=<your_license_key>                                                         │\n"
    "│   pip install --force-reinstall --no-deps {package_name:<63} │\n"
    "│                                                                                                           │\n"
    "│ For more information, please refer to the documentation.                                                  │\n"
    "└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘"
)


def generate_message_guide_sign_license(package_name: str, reason: str, license_key: str = "") -> str:
    """Generate a default message for signing the license agreement."""
    if not license_key:
        license_key = "." * 64
    return MESSAGE_GUIDE_SIGN_LICENSE.format(
        link=generate_url_user_settings(name=package_name),
        package_name=package_name,
        reason=reason.ljust(102, " "),
        license_strats=license_key[:5],
        license_ends=license_key[-5:],
    )


MESSAGE_WITH_KEY_OFFLINE = (
    "┌──────────────────────────────────────────────────────────────────────────────────────┐\n"
    "│ ⚠️ License key ({license_strats}...{license_ends}) is set, but the system is offline.                    │\n"
    "│                                                                                      │\n"
    "│ Please ensure your license key is valid and that the system is connected online.     │\n"
    "└──────────────────────────────────────────────────────────────────────────────────────┘"
)


def generate_message_with_key_offline(license_key: str) -> str:
    """Generate a message for when the license key is set but the system is offline."""
    return MESSAGE_WITH_KEY_OFFLINE.format(license_strats=license_key[:5], license_ends=license_key[-5:])


class LightningLicense:
    """This class is used to manage the license for the Lightning SDK."""

    _is_valid: Optional[bool] = None
    _license_api: Optional[LicenseApi] = None
    _stream_messages: Optional[callable] = None

    def __init__(
        self,
        name: str,
        license_key: Optional[str] = None,
        product_version: Optional[str] = None,
        product_type: str = "package",
        stream_messages: callable = print,
    ) -> None:
        self._product_name = name
        self._license_key = license_key
        self._product_version = product_version
        self.product_type = product_type
        self._is_valid = None
        self._license_api = None
        self._stream_messages = stream_messages

    @property
    def license_api(self) -> LicenseApi:
        """Get the LicenseApi instance."""
        if not self._license_api:
            with suppress(ValueError):
                self._license_api = LicenseApi()
        return self._license_api

    def validate_license(self) -> bool:
        """Validate the license key."""
        if not self.is_online():
            raise ConnectionError("No internet connection.")

        return self.license_api.valid_license(
            license_key=self.license_key,
            product_name=self.product_name,
            product_version=self.product_version,
            product_type=self.product_type,
        )

    def _auth_user_id(self) -> Tuple[Optional[str], Optional[str]]:
        """Get the authenticated user ID."""
        try:
            auth = Auth()
        except ValueError:
            return None, "No user credentials found. Please run `lightning login` to authenticate."
        return auth.user_id, None

    def _check_user_license(self, user_id: Optional[str] = None) -> bool:
        """Check if the authenticated user has a valid license for this product."""
        if not user_id:
            user_id, msg = self._auth_user_id()
            if msg:
                self._stream_messages(msg)
            if not user_id:
                return False
        if not self.license_api:
            self._stream_messages(MESSAGE_NOT_AUTHENTICATED)
            return False

        licenses = self.license_api.list_user_licenses(user_id=user_id)
        for license_info in licenses:
            if (
                license_info.product_name == self.product_name
                and license_info.product_type == self.product_type
                and license_info.is_valid
            ):
                return True
        self._stream_messages(MESSAGE_AUTH_NO_LICENSE)
        return False

    @staticmethod
    def is_online(timeout: float = 2.0) -> bool:
        """Check if the system is online by attempting to connect to a public DNS server (Google's).

        This is a simple way to check for internet connectivity.

        Args:
            timeout: The timeout for the connection attempt.
        """
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=timeout)
            return True
        except OSError:
            return False

    @property
    def is_valid(self) -> Optional[bool]:
        """Check if the license key is valid.

        license validation within package:
          - user online with valid key -> everything as now
          - user online with invalid key -> warning using wrong key + instructions
          - user online with no key -> warning for missing license approval + instructions
          - user offline with a key -> small warning  that key could not be verified
          - user offline with no key -> warning for missing license approval + instructions
        """
        if isinstance(self._is_valid, bool):
            # if the license key is already validated, return the cached value
            return self._is_valid
        is_online = self.is_online()
        if is_online:
            if self.license_key:
                self._is_valid = self.validate_license()
            else:
                # try to check if the session has logged-in user and if the user has a valid license
                self._stream_messages(
                    "Missing required license key for license validation."
                    f" Attempting to check if the authenticated user has a valid license for {self.product_name}."
                )
                user_id, auth_msg = self._auth_user_id()
                if not user_id:
                    self._is_valid = False
                    if auth_msg:
                        self._stream_messages(auth_msg)
                else:
                    self._is_valid = self._check_user_license(user_id=user_id)
        elif self.license_key:
            self._stream_messages(generate_message_with_key_offline(self.license_key))
        else:
            self._stream_messages(
                generate_message_guide_sign_license(
                    package_name=self.product_name,
                    reason="License key is not set neither cannot be found in the package root or user home.",
                )
            )

        return self._is_valid

    @property
    def has_required_details(self) -> bool:
        """Check if the license key and product name are set."""
        return bool(self.license_key and self.product_name and self.product_type)

    @staticmethod
    def _find_package_license_key(package_name: str) -> Optional[str]:
        """Find the license key in the package root as .license_key or in user home as .lightning/licenses.json.

        Args:
            package_name: The name of the package. If not provided, it will be determined from the current module.
        """
        if not package_name:
            return None
        pkg_spec = importlib.util.find_spec(package_name)
        if pkg_spec is None:
            return None
        pkg_locations = pkg_spec.submodule_search_locations
        if not pkg_locations:
            return None
        try:
            license_file = os.path.join(pkg_locations[0], ".license_key")
            with open(license_file) as fp:
                return fp.read().strip()
        except FileNotFoundError:
            return None

    @staticmethod
    def _find_user_license_key(package_name: str) -> Optional[str]:
        """Find the license key in the user home as .lightning/licenses.json.

        Args:
            package_name: The name of the package.
        """
        home = str(Path.home())
        package_name = package_name.lower()
        license_file = os.path.join(home, ".lightning", "licenses.json")
        try:
            with open(license_file) as fp:
                licenses = json.load(fp)
            # Check for the license key in the licenses.json file
            for name in (package_name, package_name.replace("-", "_"), package_name.replace("_", "-")):
                if name in licenses:
                    return licenses[name]
            return None
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    @staticmethod
    def _determine_package_version(package_name: str) -> Optional[str]:
        """Determine the product version based on the instantiation of the class.

        Args:
            package_name: The name of the package. If not provided, it will be determined from the current module.
        """
        try:
            return metadata.version(package_name)
        except metadata.PackageNotFoundError:
            return None

    @property
    def license_key(self) -> Optional[str]:
        """Get the license key."""
        name = self.product_name.replace("-", "_")
        if not self._license_key:
            # If the license key is not set, first try to find it env variables
            self._license_key = os.environ.get(f"LIGHTNING_{name.upper()}_LICENSE_KEY", None)
        if not self._license_key:
            # If the license key is not set, second try to find it in the package root
            self._license_key = self._find_package_license_key(name)
        # If not found, try to find it in the user home
        if not self._license_key:
            # If not found, try to find it in the user home
            self._license_key = self._find_user_license_key(self.product_name)
        return self._license_key

    @property
    def product_name(self) -> str:
        """Get the product name."""
        return self._product_name

    @property
    def product_version(self) -> Optional[str]:
        """Get the product version."""
        if not self._product_version and self.product_type == "package":
            self._product_version = self._determine_package_version(self.product_name.replace("-", "_"))
        return self._product_version


def check_license(
    name: str,
    license_key: Optional[str] = None,
    product_version: Optional[str] = None,
    product_type: str = "package",
    stream_messages: callable = print,
) -> None:
    """Run the license check and stream outputs.

    Args:
        name: The name of the product.
        license_key: The license key to check.
        product_version: The version of the product.
        product_type: The type of the product.
        stream_messages: A callable to stream messages.
    """
    lit_license = LightningLicense(
        name=name,
        license_key=license_key,
        product_version=product_version,
        product_type=product_type,
        stream_messages=stream_messages,
    )
    if lit_license.is_valid is False:
        stream_messages(
            generate_message_guide_sign_license(
                package_name=lit_license.product_name,
                reason="License key is not valid or not set.",
                license_key=lit_license.license_key,
            )
        )


def check_license_in_background(
    name: str,
    license_key: Optional[str] = None,
    product_version: Optional[str] = None,
    product_type: str = "package",
    stream_messages: callable = print,
) -> threading.Thread:
    """Run the license check in a background thread and stream outputs.

    Args:
        name: The name of the product.
        license_key: The license key to check.
        product_version: The version of the product.
        product_type: The type of the product.
        stream_messages: A callable to stream messages.
    """
    check_license_local = partial(
        check_license,
        name=name,
        license_key=license_key,
        product_version=product_version,
        product_type=product_type,
        stream_messages=stream_messages,
    )

    thread = threading.Thread(target=check_license_local, daemon=True)
    thread.start()
    return thread
