from typing import Optional

from lightning_sdk.lightning_cloud.rest_client import LightningClient


class LicenseApi:
    def __init__(self) -> None:
        self._client = LightningClient(retry=False, max_tries=0)

    def valid_license(
        self,
        license_key: str,
        product_name: str,
        product_version: Optional[str] = None,
    ) -> bool:
        """Check if the license key is valid.

        Args:
            license_key: The license key to check.
            product_name: The name of the product.
            product_version: The version of the product.

        Returns:
            True if the license key is valid, False otherwise.
        """
        response, code, _ = self._client.product_license_service_validate_product_license_with_http_info(
            license_key=license_key,
            product_name=product_name,
            product_version=product_version,
        )
        if code != 200:
            return False
        return response.valid
