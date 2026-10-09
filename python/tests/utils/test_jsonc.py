import pytest

from lightning_sdk.utils import jsonc

USER_CONFIG = """{
  "$schema": "https://opencode.ai/config.json",
  // my theme, "with" {braces} and // slashes
  "theme": "tokyonight",
  "provider": {
    "anthropic": { "options": { "timeout": 1000 } }, // keep me
  },
  /* block comment */
  "url": "http://example.com/*not a comment*/",
  "model": "anthropic/claude",
}
"""


def test_loads_accepts_comments_and_trailing_commas() -> None:
    assert jsonc.loads(USER_CONFIG) == {
        "$schema": "https://opencode.ai/config.json",
        "theme": "tokyonight",
        "provider": {"anthropic": {"options": {"timeout": 1000}}},
        "url": "http://example.com/*not a comment*/",
        "model": "anthropic/claude",
    }


@pytest.mark.parametrize("text", ['{"a": }', '{"a": 1', '{"a" 1}', "[1, 2", '{"a": 1} x', "/* open"])
def test_loads_rejects_invalid_documents(text: str) -> None:
    with pytest.raises(jsonc.JSONCError):
        jsonc.loads(text)


def test_set_value_only_touches_the_member() -> None:
    updated = jsonc.set_value(USER_CONFIG, ["provider", "lightning"], {"name": "Lightning AI"})

    assert jsonc.loads(updated)["provider"] == {
        "anthropic": {"options": {"timeout": 1000}},
        "lightning": {"name": "Lightning AI"},
    }
    # everything around the new member is unchanged, comments included
    assert updated.replace('    "lightning": {\n      "name": "Lightning AI"\n    },\n', "") == USER_CONFIG


def test_set_value_replaces_in_place_and_remove_restores_the_original() -> None:
    first = jsonc.set_value(USER_CONFIG, ["provider", "lightning"], {"name": "one", "models": {"a": {}}})
    second = jsonc.set_value(first, ["provider", "lightning"], {"name": "two"})

    assert jsonc.get_value(second, ["provider", "lightning"]) == {"name": "two"}
    assert jsonc.remove_value(second, ["provider", "lightning"]) == USER_CONFIG


@pytest.mark.parametrize(
    "text",
    [
        "",
        "{}",
        "{}\n",
        '{\n    "a": 1\n}\n',
        '{\n\t"a": 1,\n}\n',
        '{"a": 1}',
        '{ "provider": {} }',
        '{"provider": {"x": 1}}',
        '{\n  "provider": {\n    "x": 1 // note\n  }\n}\n',
    ],
)
def test_set_then_remove_round_trips(text: str) -> None:
    updated = jsonc.set_value(text, ["provider", "lightning"], {"k": [1, 2]})
    assert jsonc.get_value(updated, ["provider", "lightning"]) == {"k": [1, 2]}

    removed = jsonc.remove_value(updated, ["provider", "lightning"])
    assert jsonc.get_value(removed, ["provider", "lightning"]) is None
    if text.strip():
        assert jsonc.loads(removed) == jsonc.loads(text) | ({"provider": {}} if "provider" not in text else {})


def test_set_value_follows_the_file_indentation() -> None:
    updated = jsonc.set_value('{\n\t"a": 1\n}\n', ["b"], {"c": 1})
    assert updated == '{\n\t"a": 1,\n\t"b": {\n\t\t"c": 1\n\t}\n}\n'


def test_set_value_refuses_to_descend_into_a_scalar() -> None:
    with pytest.raises(jsonc.JSONCError):
        jsonc.set_value('{"provider": "oops"}', ["provider", "lightning"], {})


def test_remove_value_of_missing_member_is_a_no_op() -> None:
    assert jsonc.remove_value(USER_CONFIG, ["provider", "missing"]) == USER_CONFIG
    assert jsonc.remove_value(USER_CONFIG, ["nope", "missing"]) == USER_CONFIG


def test_remove_value_of_middle_member() -> None:
    text = '{\n  "a": 1,\n  "b": 2, // about b\n  "c": 3\n}\n'
    assert jsonc.remove_value(text, ["b"]) == '{\n  "a": 1,\n  "c": 3\n}\n'


def test_remove_value_of_last_member() -> None:
    text = '{\n  "a": 1, // about a\n  "b": 2\n}\n'
    assert jsonc.remove_value(text, ["b"]) == '{\n  "a": 1 // about a\n}\n'
