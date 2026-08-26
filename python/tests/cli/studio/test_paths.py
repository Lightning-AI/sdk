import pytest

from lightning_sdk.cli.studio.paths import parse_studio_path


def test_parse_studio_path_long_form():
    assert parse_studio_path("lit://org/teamspace/studios/my-studio/data/file.txt") == {
        "owner": "org",
        "teamspace": "teamspace",
        "studio": "my-studio",
        "destination": "data/file.txt",
    }


def test_parse_studio_path_short_form_teamspace():
    result = parse_studio_path("lit://teamspace/studios/my-studio/file.txt")
    assert (result["owner"], result["teamspace"], result["studio"], result["destination"]) == (
        None,
        "teamspace",
        "my-studio",
        "file.txt",
    )


def test_parse_studio_path_short_form_bare_studio():
    result = parse_studio_path("lit://my-studio/file.txt")
    assert (result["owner"], result["teamspace"], result["studio"], result["destination"]) == (
        None,
        None,
        "my-studio",
        "file.txt",
    )


def test_parse_studio_path_relative_form():
    result = parse_studio_path("lit:///studios/my-studio/data/file.txt")
    assert (result["owner"], result["teamspace"], result["studio"], result["destination"]) == (
        None,
        None,
        "my-studio",
        "data/file.txt",
    )


def test_parse_studio_path_relative_form_studio_root():
    result = parse_studio_path("lit:///studios/my-studio/")
    assert (result["studio"], result["destination"]) == ("my-studio", "")


def test_parse_studio_path_relative_form_missing_studio_raises():
    with pytest.raises(ValueError, match="Missing studio name"):
        parse_studio_path("lit:///studios/")


def test_parse_studio_path_relative_form_requires_studios_root():
    with pytest.raises(ValueError, match="lit:///studios/<studio>/<path>"):
        parse_studio_path("lit:///uploads/file.txt")


def test_parse_studio_path_studio_root_without_trailing_slash_raises():
    with pytest.raises(ValueError, match="add a trailing '/'"):
        parse_studio_path("lit://org/teamspace/studios/my-studio")


def test_parse_studio_path_bare_absolute_path_raises():
    with pytest.raises(ValueError, match="Invalid studio path"):
        parse_studio_path("/tmp/file")


def test_parse_studio_path_extra_slashes_raise():
    with pytest.raises(ValueError, match="Invalid studio path"):
        parse_studio_path("lit:////studios/my-studio/file.txt")
