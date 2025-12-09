from lightning_sdk.api.utils import _get_cloud_url as _cloud_url
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import ProductLicenseServiceApi, ProductLicenseServiceValidateLicenseBody


class LicenseApi:
    def __init__(self, login_token: str) -> None:
        self._cloud_url = _cloud_url()
        self._auth = Auth()
        self._auth.token_login(login_token, save_token=True)
        self._client = self._auth.create_api_client()
        self._api = ProductLicenseServiceApi(self._client)

    def validate_license(self, license_key: str, product_id: str) -> bool:
        """Validate a license key for a specific product.

        Args:
            license_key: The license key to validate
            product_id: The product ID

        Returns:
            bool: True if license is valid, False otherwise

        Raises:
            Exception: If license validation fails
        """
        try:
            response = self._api.product_license_service_validate_license(
                body=ProductLicenseServiceValidateLicenseBody(product_id=product_id), license_key=license_key
            )
            return response.is_valid
        except Exception:
            raise InvalidLicenseError(f"Invalid license key {license_key} for product {product_id}") from None


class InvalidLicenseError(Exception):
    pass
