from unittest.mock import Mock, patch

import pytest

from lightning_sdk.api.license_api import InvalidLicenseError, LicenseApi


# Test fixtures
@pytest.fixture()
def test_token():
    """Test authentication token."""
    return "test-auth-token"


@pytest.fixture()
def test_license_key():
    """Test license key."""
    return "test-license-key-123"


@pytest.fixture()
def test_product_id():
    """Test product ID."""
    return "test-product-456"


# LicenseApi Tests
@patch("lightning_sdk.api.license_api.Auth")
@patch("lightning_sdk.api.license_api.ProductLicenseServiceApi")
@patch("lightning_sdk.api.license_api._cloud_url")
def test_license_api_initialization(mock_cloud_url, mock_api_class, mock_auth_class, test_token):
    mock_cloud_url.return_value = "https://test.lightning.ai"
    mock_auth_instance = Mock()
    mock_auth_class.return_value = mock_auth_instance
    mock_client = Mock()
    mock_auth_instance.create_api_client.return_value = mock_client
    mock_api_instance = Mock()
    mock_api_class.return_value = mock_api_instance

    license_api = LicenseApi(test_token)

    mock_auth_class.assert_called_once()
    mock_auth_instance.token_login.assert_called_once_with(test_token, save_token=True)
    mock_auth_instance.create_api_client.assert_called_once()
    mock_api_class.assert_called_once_with(mock_client)
    assert license_api._api == mock_api_instance


@patch("lightning_sdk.api.license_api.Auth")
@patch("lightning_sdk.api.license_api.ProductLicenseServiceApi")
@patch("lightning_sdk.api.license_api._cloud_url")
def test_validate_license_success(
    mock_cloud_url, mock_api_class, mock_auth_class, test_token, test_license_key, test_product_id
):
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

    license_api = LicenseApi(test_token)

    result = license_api.validate_license(test_license_key, test_product_id)

    assert result is True
    mock_api_instance.product_license_service_validate_license.assert_called_once()
    call_args = mock_api_instance.product_license_service_validate_license.call_args
    assert call_args[1]["license_key"] == test_license_key
    assert call_args[1]["body"].product_id == test_product_id


@patch("lightning_sdk.api.license_api.Auth")
@patch("lightning_sdk.api.license_api.ProductLicenseServiceApi")
@patch("lightning_sdk.api.license_api._cloud_url")
def test_validate_license_invalid(
    mock_cloud_url, mock_api_class, mock_auth_class, test_token, test_license_key, test_product_id
):
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

    license_api = LicenseApi(test_token)

    result = license_api.validate_license(test_license_key, test_product_id)

    assert result is False


@patch("lightning_sdk.api.license_api.Auth")
@patch("lightning_sdk.api.license_api.ProductLicenseServiceApi")
@patch("lightning_sdk.api.license_api._cloud_url")
def test_validate_license_api_exception(
    mock_cloud_url, mock_api_class, mock_auth_class, test_token, test_license_key, test_product_id
):
    mock_cloud_url.return_value = "https://test.lightning.ai"
    mock_auth_instance = Mock()
    mock_auth_class.return_value = mock_auth_instance
    mock_client = Mock()
    mock_auth_instance.create_api_client.return_value = mock_client
    mock_api_instance = Mock()
    mock_api_class.return_value = mock_api_instance

    mock_api_instance.product_license_service_validate_license.side_effect = Exception("API Error")

    license_api = LicenseApi(test_token)

    with pytest.raises(InvalidLicenseError) as exc_info:
        license_api.validate_license(test_license_key, test_product_id)

    assert str(exc_info.value) == f"Invalid license key {test_license_key} for product {test_product_id}"


@patch("lightning_sdk.api.license_api.Auth")
@patch("lightning_sdk.api.license_api.ProductLicenseServiceApi")
@patch("lightning_sdk.api.license_api._cloud_url")
def test_validate_license_with_empty_product_id(
    mock_cloud_url, mock_api_class, mock_auth_class, test_token, test_license_key
):
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

    license_api = LicenseApi(test_token)

    result = license_api.validate_license(test_license_key, "")

    assert result is True
    call_args = mock_api_instance.product_license_service_validate_license.call_args
    assert call_args[1]["body"].product_id == ""


@patch("lightning_sdk.api.license_api.Auth")
@patch("lightning_sdk.api.license_api.ProductLicenseServiceApi")
@patch("lightning_sdk.api.license_api._cloud_url")
def test_validate_license_with_special_characters(mock_cloud_url, mock_api_class, mock_auth_class, test_token):
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

    special_license_key = "test-license-key-with-special-chars-!@#$%"
    special_product_id = "product-with-special-chars-!@#$%"

    license_api = LicenseApi(test_token)

    result = license_api.validate_license(special_license_key, special_product_id)

    assert result is True
    call_args = mock_api_instance.product_license_service_validate_license.call_args
    assert call_args[1]["license_key"] == special_license_key
    assert call_args[1]["body"].product_id == special_product_id


@patch("lightning_sdk.api.license_api.Auth")
@patch("lightning_sdk.api.license_api.ProductLicenseServiceApi")
@patch("lightning_sdk.api.license_api._cloud_url")
def test_validate_license_network_error(
    mock_cloud_url, mock_api_class, mock_auth_class, test_token, test_license_key, test_product_id
):
    mock_cloud_url.return_value = "https://test.lightning.ai"
    mock_auth_instance = Mock()
    mock_auth_class.return_value = mock_auth_instance
    mock_client = Mock()
    mock_auth_instance.create_api_client.return_value = mock_client
    mock_api_instance = Mock()
    mock_api_class.return_value = mock_api_instance

    mock_api_instance.product_license_service_validate_license.side_effect = ConnectionError("Network error")

    license_api = LicenseApi(test_token)

    with pytest.raises(InvalidLicenseError) as exc_info:
        license_api.validate_license(test_license_key, test_product_id)

    assert str(exc_info.value) == f"Invalid license key {test_license_key} for product {test_product_id}"


def test_invalid_license_error_creation():
    error_message = "Test license error"

    with pytest.raises(InvalidLicenseError) as exc_info:
        raise InvalidLicenseError(error_message)

    assert str(exc_info.value) == error_message


def test_invalid_license_error_inheritance():
    assert issubclass(InvalidLicenseError, Exception)
