from functools import lru_cache

from lightning_sdk.api.license_api import LicenseApi


class License:
    def __init__(self, license_key: str, product_name: str) -> None:
        self.license_key = license_key
        self.product_name = product_name

    @lru_cache(maxsize=1)  # noqa: B019
    def validate(self) -> bool:
        return LicenseApi(self.license_key).validate_license(self.license_key, self.product_name)
