from unittest.mock import ANY, MagicMock, mock_open, patch

import pytest

from lightning_sdk.lightning_cloud.openapi import V1ProductLicense
from lightning_sdk.services.license import LightningLicense, check_license


@patch("importlib.metadata.version")
def test_determine_package_version_found(mock_metadata_version):
    mock_metadata_version.return_value = "0.1.0"
    result = LightningLicense._determine_package_version("any")
    mock_metadata_version.assert_called_once_with(ANY)
    assert result == "0.1.0"


@patch("importlib.util.find_spec")
@patch("builtins.open", new_callable=mock_open, read_data="test_key")
def test_find_package_license_key_found(mock_open, mock_find_spec):
    mock_spec = MagicMock()
    mock_spec.submodule_search_locations = ["/any/package"]
    mock_find_spec.return_value = mock_spec
    assert LightningLicense._find_package_license_key("any") == "test_key"
    mock_find_spec.assert_called_once_with("any")
    mock_open.assert_called_once_with("/any/package/.license_key")


@patch("importlib.util.find_spec")
@patch("builtins.open", side_effect=FileNotFoundError)
def test_find_package_license_key_no_file(mock_open, mock_find_spec):
    mock_spec = MagicMock()
    mock_spec.submodule_search_locations = ["/any/package"]
    mock_find_spec.return_value = mock_spec
    assert LightningLicense._find_package_license_key("any") is None
    mock_find_spec.assert_called_once_with("any")
    mock_open.assert_called_once_with("/any/package/.license_key")


@patch("pathlib.Path.home", return_value="/fake/home")
@patch("builtins.open", new_callable=mock_open, read_data='{"abc": "user_key"}')
def test_find_user_license_key_found(mock_open, mock_home):
    assert LightningLicense._find_user_license_key("abc") == "user_key"
    assert mock_open.call_count == 1
    assert mock_home.call_count == 1


@patch("pathlib.Path.home", return_value="/fake/home")
@patch("builtins.open", side_effect=FileNotFoundError)
def test_find_user_license_key_missing(mock_open, mock_home):
    assert LightningLicense._find_user_license_key("abc") is None
    assert mock_open.call_count == 1
    assert mock_home.call_count == 1


@patch("importlib.metadata.version")
@pytest.mark.parametrize("license_source", ["package", "user"])
def test_license_autofilled_properties(mock_metadata_version, license_source):
    mock_metadata_version.return_value = "0.1.0"
    if license_source == "package":
        LightningLicense._find_package_license_key = MagicMock(return_value="package_key")
        LightningLicense._find_user_license_key = MagicMock()
    else:
        LightningLicense._find_package_license_key = MagicMock(return_value=None)
        LightningLicense._find_user_license_key = MagicMock(return_value="user_key")

    lit_license = LightningLicense("abc")
    assert lit_license.product_name == "abc"
    assert lit_license.product_version == "0.1.0"
    assert lit_license.license_key == f"{license_source}_key"


@patch("lightning_sdk.services.license.LicenseApi")
def test_validate_license_with_all_attributes(mock_api_cls):
    mock_api = MagicMock()
    mock_api.valid_license.return_value = True
    mock_api_cls.return_value = mock_api

    lit_license = LightningLicense(
        name="test_product",
        license_key="test_key",
        product_version="1.2.3",
    )
    # Patch is_online to always return True
    with patch.object(LightningLicense, "is_online", return_value=True):
        assert lit_license.validate_license() is True
        mock_api.valid_license.assert_called_once_with(
            license_key="test_key", product_name="test_product", product_version="1.2.3", product_type="package"
        )


def test_check_license_valid(monkeypatch):
    mock_license_instance = MagicMock(is_valid=True)
    mock_license = MagicMock(return_value=mock_license_instance)
    monkeypatch.setattr("lightning_sdk.services.license.LightningLicense", mock_license)
    mock_stream_messages = MagicMock()

    check_license("test_product", "valid_key", stream_messages=mock_stream_messages)

    mock_license.assert_called_once_with(
        name="test_product",
        license_key="valid_key",
        product_version=None,
        product_type="package",
        stream_messages=mock_stream_messages,
    )
    mock_stream_messages.assert_not_called()


def test_check_license_invalid(monkeypatch):
    mock_license_instance = MagicMock(is_valid=False)
    mock_license = MagicMock(return_value=mock_license_instance)
    monkeypatch.setattr("lightning_sdk.services.license.LightningLicense", mock_license)
    mock_stream_messages = MagicMock()

    check_license("test_product", "any_key", stream_messages=mock_stream_messages)

    mock_license.assert_called_once_with(
        name="test_product",
        license_key="any_key",
        product_version=None,
        product_type="package",
        stream_messages=mock_stream_messages,
    )
    mock_stream_messages.assert_called_once()
    assert "License key is not valid." in mock_stream_messages.call_args[0][0]


def test_check_license_in_background_demo():
    from lightning_sdk.services.license import check_license_in_background

    thread = check_license_in_background("abc")
    thread.join(timeout=2)


@patch("lightning_sdk.services.license.LicenseApi")
@patch("lightning_sdk.services.license.Auth")
def test_check_user_license_valid(mock_auth, mock_license_api):
    """1. User is authenticated, and a valid license for the product exists."""
    mock_auth_instance = mock_auth.return_value
    mock_auth_instance.load.return_value = True
    mock_auth_instance.user_id = "test_user"
    mock_auth_instance.api_key = "test_api_key"

    mock_license_api_instance = mock_license_api.return_value
    mock_license_api_instance.list_user_licenses.return_value = [
        V1ProductLicense(product_name="test_product", product_type="package", is_valid=True),
        V1ProductLicense(product_name="other_product", product_type="package", is_valid=True),
    ]

    lit_license = LightningLicense(name="test_product", product_type="package")
    lit_license._license_api = mock_license_api_instance  # Assign mocked API
    assert lit_license._check_user_license() is True
    mock_auth_instance.load.assert_called_once()
    mock_license_api_instance.list_user_licenses.assert_called_once_with(user_id="test_user")


@patch("lightning_sdk.services.license.LicenseApi")
@patch("lightning_sdk.services.license.Auth")
def test_check_user_license_no_matching_product(mock_auth, mock_license_api):
    """2. User is authenticated, but no license for the product exists."""
    mock_auth_instance = mock_auth.return_value
    mock_auth_instance.load.return_value = True
    mock_auth_instance.user_id = "test_user"
    mock_auth_instance.api_key = "test_api_key"

    mock_license_api_instance = mock_license_api.return_value
    mock_license_api_instance.list_user_licenses.return_value = [
        V1ProductLicense(product_name="other_product", product_type="package", is_valid=True),
    ]
    mock_stream_messages = MagicMock()

    lit_license = LightningLicense(name="test_product", product_type="package", stream_messages=mock_stream_messages)
    lit_license._license_api = mock_license_api_instance
    assert lit_license._check_user_license() is False
    mock_auth_instance.load.assert_called_once()
    mock_license_api_instance.list_user_licenses.assert_called_once_with(user_id="test_user")
    mock_stream_messages.assert_not_called()  # No message if license not found but user is auth


@patch("lightning_sdk.services.license.LicenseApi")
@patch("lightning_sdk.services.license.Auth")
def test_check_user_license_invalid_license_for_product(mock_auth, mock_license_api):
    """3. User is authenticated, but the existing license for the product is invalid."""
    mock_auth_instance = mock_auth.return_value
    mock_auth_instance.load.return_value = True
    mock_auth_instance.user_id = "test_user"
    mock_auth_instance.api_key = "test_api_key"

    mock_license_api_instance = mock_license_api.return_value
    mock_license_api_instance.list_user_licenses.return_value = [
        V1ProductLicense(product_name="test_product", product_type="package", is_valid=False),
    ]
    mock_stream_messages = MagicMock()

    lit_license = LightningLicense(name="test_product", product_type="package", stream_messages=mock_stream_messages)
    lit_license._license_api = mock_license_api_instance
    assert lit_license._check_user_license() is False
    mock_auth_instance.load.assert_called_once()
    mock_license_api_instance.list_user_licenses.assert_called_once_with(user_id="test_user")
    mock_stream_messages.assert_not_called()  # No message if license invalid but user is auth


@patch("lightning_sdk.services.license.LicenseApi")
@patch("lightning_sdk.services.license.Auth")
def test_check_user_license_not_authenticated(mock_auth, mock_license_api):
    """4. User is not authenticated (no credentials found)."""
    mock_auth_instance = mock_auth.return_value
    mock_auth_instance.load.return_value = False  # Simulate no credentials
    mock_stream_messages = MagicMock()
    mock_license_api_instance = mock_license_api.return_value

    lit_license = LightningLicense(name="test_product", stream_messages=mock_stream_messages)
    lit_license._license_api = mock_license_api_instance
    assert lit_license._check_user_license() is False
    mock_auth_instance.load.assert_called_once()
    mock_license_api_instance.list_user_licenses.assert_not_called()
    mock_stream_messages.assert_called_once_with(
        "No user credentials found. Please run `lightning login` to authenticate."
    )


@pytest.mark.parametrize(("param_user_id", "param_api_key"), [(None, "test_api_key"), ("test_user", None)])
@patch("lightning_sdk.services.license.LicenseApi")
@patch("lightning_sdk.services.license.Auth")
def test_check_user_license_missing_auth_details(mock_auth, mock_license_api, param_user_id, param_api_key):
    """5. User is authenticated, but user_id or api_key is missing."""
    mock_auth_instance = mock_auth.return_value
    mock_auth_instance.load.return_value = True
    mock_auth_instance.user_id = param_user_id
    mock_auth_instance.api_key = param_api_key
    mock_stream_messages = MagicMock()
    mock_license_api_instance = mock_license_api.return_value

    lit_license = LightningLicense(name="test_product", stream_messages=mock_stream_messages)
    lit_license._license_api = mock_license_api_instance

    assert lit_license._check_user_license() is False
    mock_auth_instance.load.assert_called_once()
    mock_license_api_instance.list_user_licenses.assert_not_called()
    mock_stream_messages.assert_called_once_with(
        "User ID or API key is missing. Please run `lightning login` to authenticate."
    )
