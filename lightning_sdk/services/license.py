import importlib
import json
import os
import socket
import threading
from functools import partial
from pathlib import Path
from typing import Optional

from lightning_sdk.api.license_api import LicenseApi


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

    def validate_license(self) -> bool:
        """Validate the license key."""
        if not self.is_online():
            raise ConnectionError("No internet connection.")

        self._license_api = LicenseApi()
        return self._license_api.valid_license(
            license_key=self.license_key,
            product_name=self.product_name,
            product_version=self.product_version,
            product_type=self.product_type,
        )

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
        if not self.product_version:
            self._stream_messages("Product version is not set correctly, consider leave it empty for auto-determine.")
        if not self.license_key:
            self._stream_messages(
                "License key is not set neither cannot be found in the package root or user home."
                " Please make sure you have signed the license agreement and set the license key."
                " For more information, please refer to the documentation.",
            )
        is_online = self.is_online()
        if self.license_key and is_online:
            self._is_valid = self.validate_license()
        elif not is_online:
            self._stream_messages(
                "License key is set but the system is offline. "
                "Please make sure you have a valid license key and the system is online."
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
        try:
            pkg_locations = importlib.util.find_spec(package_name).submodule_search_locations
            if not pkg_locations:
                return None
            license_file = os.path.join(pkg_locations[0], ".license_key")
            with open(license_file) as fp:
                return fp.read().strip()
        except (FileNotFoundError, ModuleNotFoundError):
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
            pkg = importlib.import_module(package_name)
            return getattr(pkg, "__version__", None)
        except ImportError:
            return None

    @property
    def license_key(self) -> Optional[str]:
        """Get the license key."""
        if not self._license_key:
            # If the license key is not set, fist try to find it in the package root
            self._license_key = self._find_package_license_key(self.product_name.replace("-", "_"))
            # If not found, try to find it in the user home
            if not self._license_key:
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
            "License key is not valid.\n"
            f" Key: {lit_license.license_key}\n"
            " Please make sure you have a valid license key."
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
