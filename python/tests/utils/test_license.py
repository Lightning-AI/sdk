from unittest.mock import Mock, patch

import pytest

from lightning_sdk.api.license_api import InvalidLicenseError
from lightning_sdk.utils.license import License


# Test fixtures
@pytest.fixture()
def test_license_key():
    """Test license key."""
    return "test-license-key-123"


@pytest.fixture()
def test_product_name():
    """Test product name."""
    return "test-product-456"


@patch("lightning_sdk.utils.license.LicenseApi")
def test_license_initialization(mock_license_api_class, test_license_key, test_product_name):
    mock_license_api_instance = Mock()
    mock_license_api_class.return_value = mock_license_api_instance

    license_obj = License(test_license_key, test_product_name)

    assert license_obj.license_key == test_license_key
    assert license_obj.product_name == test_product_name


@patch("lightning_sdk.utils.license.LicenseApi")
def test_validate_success(mock_license_api_class, test_license_key, test_product_name):
    mock_license_api_instance = Mock()
    mock_license_api_instance.validate_license.return_value = True
    mock_license_api_class.return_value = mock_license_api_instance

    license_obj = License(test_license_key, test_product_name)

    result = license_obj.validate()

    assert result is True
    mock_license_api_class.assert_called_once_with(test_license_key)
    mock_license_api_instance.validate_license.assert_called_once_with(test_license_key, test_product_name)


@patch("lightning_sdk.utils.license.LicenseApi")
def test_validate_failure(mock_license_api_class, test_license_key, test_product_name):
    mock_license_api_instance = Mock()
    mock_license_api_instance.validate_license.return_value = False
    mock_license_api_class.return_value = mock_license_api_instance

    license_obj = License(test_license_key, test_product_name)

    result = license_obj.validate()

    assert result is False


@patch("lightning_sdk.utils.license.LicenseApi")
def test_validate_caching(mock_license_api_class, test_license_key, test_product_name):
    mock_license_api_instance = Mock()
    mock_license_api_instance.validate_license.return_value = True
    mock_license_api_class.return_value = mock_license_api_instance

    license_obj = License(test_license_key, test_product_name)

    result1 = license_obj.validate()
    result2 = license_obj.validate()
    result3 = license_obj.validate()

    assert result1 is True
    assert result2 is True
    assert result3 is True

    mock_license_api_class.assert_called_once_with(test_license_key)
    mock_license_api_instance.validate_license.assert_called_once_with(test_license_key, test_product_name)


@patch("lightning_sdk.utils.license.LicenseApi")
def test_validate_exception_handling(mock_license_api_class, test_license_key, test_product_name):
    mock_license_api_instance = Mock()
    mock_license_api_instance.validate_license.side_effect = InvalidLicenseError("Test error")
    mock_license_api_class.return_value = mock_license_api_instance

    license_obj = License(test_license_key, test_product_name)

    with pytest.raises(InvalidLicenseError) as exc_info:
        license_obj.validate()

    assert str(exc_info.value) == "Test error"


@patch("lightning_sdk.utils.license.LicenseApi")
def test_validate_with_different_products(mock_license_api_class, test_license_key):
    mock_license_api_instance = Mock()
    mock_license_api_instance.validate_license.return_value = True
    mock_license_api_class.return_value = mock_license_api_instance

    license_obj1 = License(test_license_key, "product-1")
    license_obj2 = License(test_license_key, "product-2")

    result1 = license_obj1.validate()
    result2 = license_obj2.validate()

    assert result1 is True
    assert result2 is True

    assert mock_license_api_class.call_count == 2
    mock_license_api_instance.validate_license.assert_any_call(test_license_key, "product-1")
    mock_license_api_instance.validate_license.assert_any_call(test_license_key, "product-2")


@patch("lightning_sdk.utils.license.LicenseApi")
def test_license_caching_with_different_instances(mock_license_api_class, test_license_key):
    mock_license_api_instance = Mock()
    mock_license_api_instance.validate_license.return_value = True
    mock_license_api_class.return_value = mock_license_api_instance

    license_obj1 = License(test_license_key, "product-1")
    license_obj2 = License(test_license_key, "product-1")  # Same parameters

    result1 = license_obj1.validate()
    result2 = license_obj2.validate()

    assert result1 is True
    assert result2 is True

    assert mock_license_api_class.call_count == 2
    assert mock_license_api_instance.validate_license.call_count == 2


@patch("lightning_sdk.utils.license.LicenseApi")
def test_license_with_special_characters(mock_license_api_class):
    mock_license_api_instance = Mock()
    mock_license_api_instance.validate_license.return_value = True
    mock_license_api_class.return_value = mock_license_api_instance

    special_license_key = "test-license-key-with-special-chars-!@#$%"
    special_product_name = "product-with-special-chars-!@#$%"

    license_obj = License(special_license_key, special_product_name)

    result = license_obj.validate()

    assert result is True
    mock_license_api_class.assert_called_once_with(special_license_key)
    mock_license_api_instance.validate_license.assert_called_once_with(special_license_key, special_product_name)


@patch("lightning_sdk.utils.license.LicenseApi")
def test_license_validation_with_empty_product_name(mock_license_api_class, test_license_key):
    mock_license_api_instance = Mock()
    mock_license_api_instance.validate_license.return_value = True
    mock_license_api_class.return_value = mock_license_api_instance

    license_obj = License(test_license_key, "")

    result = license_obj.validate()

    assert result is True
    mock_license_api_class.assert_called_once_with(test_license_key)
    mock_license_api_instance.validate_license.assert_called_once_with(test_license_key, "")
