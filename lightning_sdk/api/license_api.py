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
        response, code, _ = self._client.product_license_service_validate_product_license_with_http_info(
            license_key=license_key,
            product_name=product_name,
            product_version=product_version,
            product_type=product_type,
        )
        if code != 200:
            raise ConnectionError(f"Failed to validate license key: {code} - {response}")
        return response.valid

    def list_user_licenses(self, user_id: str) -> list:
        """List all licenses for a user.

        Args:
            user_id: The ID of the user.

        Returns:
            A list of licenses for the user.
        """
        response = self._client.product_license_service_list_user_licenses(user_id=user_id)
        return response.licenses
