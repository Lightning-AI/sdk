import pytest

from lightning_sdk.cli.cp import parse_lit_url


def test_parse_lit_url_missing_scheme():
    with pytest.raises(ValueError, match="URL must start with 'lit://"):
        parse_lit_url("teamspace/org/studios/my-studio")


def test_parse_lit_url_studios():
    assert parse_lit_url("lit://org/teamspace/studios/my-studio") == "studios"


def test_parse_lit_url_uploads():
    assert parse_lit_url("lit://org/teamspace/uploads/my-file") == "uploads"


def test_parse_lit_url_s3_folders():
    assert parse_lit_url("lit://org/teamspace/s3_folders/my-folder") == "s3_folders"


def test_parse_lit_url_lightning_storage():
    assert parse_lit_url("lit://org/teamspace/lightning_storage/my-data") == "lightning_storage"


def test_parse_lit_url_missing_resource_type():
    with pytest.raises(ValueError, match="Expected a resource type after the teamspace"):
        parse_lit_url("lit://org/teamspace")


def test_parse_lit_url_relative_form():
    assert parse_lit_url("lit:///uploads/my-file") == "uploads"


def test_parse_lit_url_relative_form_missing_resource_type():
    with pytest.raises(ValueError, match="Expected a resource type"):
        parse_lit_url("lit:///")
