from unittest.mock import MagicMock, mock_open, patch

import pytest

from lightning_sdk.services.license import LightningLicense, check_license


@patch("lightning_sdk.services.license.importlib.import_module")
def test_determine_package_version_found(mock_import):
    mock_pkg = MagicMock(__version__="0.1.0")
    mock_import.return_value = mock_pkg
    assert LightningLicense._determine_package_version("any") == "0.1.0"


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


@patch("lightning_sdk.services.license.importlib.import_module")
@pytest.mark.parametrize("license_source", ["package", "user"])
def test_license_autofilled_properties(mock_import, license_source):
    mock_pkg = MagicMock(__version__="0.1.0")
    mock_import.return_value = mock_pkg
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
