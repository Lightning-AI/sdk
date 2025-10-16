"""
Integration tests for license validation functionality.

This module tests the complete license validation workflow from the License
utility class through the LicenseApi to the ProductLicenseServiceApi.
"""

from unittest.mock import Mock, patch

import pytest

from lightning_sdk.api.license_api import InvalidLicenseError
from lightning_sdk.utils.license import License


@patch("lightning_sdk.api.license_api.Auth")
@patch("lightning_sdk.api.license_api.ProductLicenseServiceApi")
@patch("lightning_sdk.api.license_api._cloud_url")
def test_full_license_validation_workflow(mock_cloud_url, mock_api_class, mock_auth_class):
    """Test the complete license validation workflow."""
    # Arrange
    mock_cloud_url.return_value = "https://test.lightning.ai"
    mock_auth_instance = Mock()
    mock_auth_class.return_value = mock_auth_instance
    mock_client = Mock()
    mock_auth_instance.create_api_client.return_value = mock_client
    mock_api_instance = Mock()
    mock_api_class.return_value = mock_api_instance

    mock_response = Mock()
    mock_response.is_valid = True
    mock_api_instance.product_license_service_validate_license.return_value = mock_response

    license_key = "integration-test-license"
    product_name = "integration-test-product"

    # Act
    license_obj = License(license_key, product_name)
    result = license_obj.validate()

    # Assert
    assert result is True
    mock_auth_instance.token_login.assert_called_once_with(license_key, save_token=True)
    mock_api_instance.product_license_service_validate_license.assert_called_once()


@patch("lightning_sdk.api.license_api.Auth")
@patch("lightning_sdk.api.license_api.ProductLicenseServiceApi")
@patch("lightning_sdk.api.license_api._cloud_url")
def test_full_license_validation_workflow_failure(mock_cloud_url, mock_api_class, mock_auth_class):
    """Test the complete license validation workflow with failure."""
    # Arrange
    mock_cloud_url.return_value = "https://test.lightning.ai"
    mock_auth_instance = Mock()
    mock_auth_class.return_value = mock_auth_instance
    mock_client = Mock()
    mock_auth_instance.create_api_client.return_value = mock_client
    mock_api_instance = Mock()
    mock_api_class.return_value = mock_api_instance

    mock_response = Mock()
    mock_response.is_valid = False
    mock_api_instance.product_license_service_validate_license.return_value = mock_response

    license_key = "integration-test-license-invalid"
    product_name = "integration-test-product"

    # Act
    license_obj = License(license_key, product_name)
    result = license_obj.validate()

    # Assert
    assert result is False
    mock_auth_instance.token_login.assert_called_once_with(license_key, save_token=True)
    mock_api_instance.product_license_service_validate_license.assert_called_once()


@patch("lightning_sdk.api.license_api.Auth")
@patch("lightning_sdk.api.license_api.ProductLicenseServiceApi")
@patch("lightning_sdk.api.license_api._cloud_url")
def test_full_license_validation_workflow_exception(mock_cloud_url, mock_api_class, mock_auth_class):
    """Test the complete license validation workflow with exception."""
    # Arrange
    mock_cloud_url.return_value = "https://test.lightning.ai"
    mock_auth_instance = Mock()
    mock_auth_class.return_value = mock_auth_instance
    mock_client = Mock()
    mock_auth_instance.create_api_client.return_value = mock_client
    mock_api_instance = Mock()
    mock_api_class.return_value = mock_api_instance

    # Mock API exception
    mock_api_instance.product_license_service_validate_license.side_effect = Exception("API Error")

    license_key = "integration-test-license-error"
    product_name = "integration-test-product"

    # Act & Assert
    license_obj = License(license_key, product_name)
    with pytest.raises(InvalidLicenseError) as exc_info:
        license_obj.validate()

    assert str(exc_info.value) == f"Invalid license key {license_key} for product {product_name}"
    mock_auth_instance.token_login.assert_called_once_with(license_key, save_token=True)
    mock_api_instance.product_license_service_validate_license.assert_called_once()
