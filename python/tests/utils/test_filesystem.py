import pytest

from lightning_sdk.utils.filesystem import parse_lit_url


def test_parse_lit_url_long_form():
    assert parse_lit_url("lit://org/teamspace/uploads/data.csv") == {
        "owner": "org",
        "teamspace": "teamspace",
        "studio": None,
        "destination": "uploads/data.csv",
    }


def test_parse_lit_url_long_form_teamspace_root():
    result = parse_lit_url("lit://org/teamspace")
    assert (result["owner"], result["teamspace"], result["destination"]) == ("org", "teamspace", "")


def test_parse_lit_url_bare_path_without_prefix():
    result = parse_lit_url("org/teamspace/uploads/data.csv")
    assert (result["owner"], result["teamspace"], result["destination"]) == ("org", "teamspace", "uploads/data.csv")


def test_parse_lit_url_relative_form():
    assert parse_lit_url("lit:///uploads/data.csv") == {
        "owner": None,
        "teamspace": None,
        "studio": None,
        "destination": "uploads/data.csv",
    }


def test_parse_lit_url_relative_form_nested():
    result = parse_lit_url("lit:///studios/my-studio/notes.txt")
    assert (result["owner"], result["teamspace"], result["destination"]) == (None, None, "studios/my-studio/notes.txt")


def test_parse_lit_url_relative_form_teamspace_root():
    result = parse_lit_url("lit:///")
    assert (result["owner"], result["teamspace"], result["destination"]) == (None, None, "")


def test_parse_lit_url_single_segment_suggests_relative_form():
    with pytest.raises(ValueError, match="lit:///<path>"):
        parse_lit_url("lit://data.csv")


def test_parse_lit_url_empty_raises():
    with pytest.raises(ValueError, match="cannot be empty"):
        parse_lit_url("lit://")


def test_parse_lit_url_bare_absolute_path_raises():
    with pytest.raises(ValueError, match="Invalid lit URL"):
        parse_lit_url("/tmp/file")


def test_parse_lit_url_extra_slashes_raise():
    with pytest.raises(ValueError, match="Invalid lit URL"):
        parse_lit_url("lit:////uploads/data.csv")
