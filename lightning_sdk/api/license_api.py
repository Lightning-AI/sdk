import os
from typing import Optional
from urllib.parse import urlencode

from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.rest_client import LightningClient

LICENSE_CODE = os.environ.get("LICENSE_CODE", "d9s79g79ss")
# https://lightning.ai/home?settings=licenses
LICENSE_SIGNING_URL = f"{env.LIGHTNING_CLOUD_URL}?settings=licenses"


def generate_url_user_settings(name: str, redirect_to: str = LICENSE_SIGNING_URL) -> str:
    params = urlencode({"redirectTo": redirect_to, "okbhrt": LICENSE_CODE, "licenseName": name})
    return f"{env.LIGHTNING_CLOUD_URL}/sign-in?{params}"


class LicenseApi:
    _client_authenticated: LightningClient = None
    _client_public: LightningClient = None

    @property
    def client_public(self) -> LightningClient:
        if not self._client_public:
            self._client_public = LightningClient(retry=False, max_tries=0, with_auth=False)
        return self._client_public

    @property
    def client_authenticated(self) -> LightningClient:
        if not self._client_authenticated:
            self._client_authenticated = LightningClient(retry=True, max_tries=3, with_auth=True)
        return self._client_authenticated

    def valid_license(
        self,
        license_key: str,
        product_name: str,
        product_version: Optional[str] = None,
        product_type: str = "package",
    ) -> bool:
        """Check if the license key is valid.

        Args:
            license_key: The license key to check.
            product_name: The name of the product.
            product_version: The version of the product.
            product_type: The type of the product. Default is "package".

        Returns:
            True if the license key is valid, False otherwise.
        """
        response = self.client_public.product_license_service_validate_product_license(
            license_key=license_key,
            product_name=product_name,
            product_version=product_version,
            product_type=product_type,
        )
        return response.valid

    def list_user_licenses(self, user_id: str) -> list:
        """List all licenses for a user.

        Args:
            user_id: The ID of the user.

        Returns:
            A list of licenses for the user.
        """
        response = self.client_authenticated.product_license_service_list_user_licenses(user_id=user_id)
        return response.licenses
