import io

import pytest
import rich_click as click

from lightning_sdk.api.deployment_api import Env, Secret
from lightning_sdk.cli.utils.configuration import (
    deployment_environment_records,
    environment_records,
    parse_assignment,
    read_secret_value,
    secret_records,
)


def test_parse_assignment_splits_once_and_preserves_empty_value():
    assert parse_assignment("TOKEN=part=two") == ("TOKEN", "part=two")
    assert parse_assignment("_EMPTY=") == ("_EMPTY", "")


@pytest.mark.parametrize("assignment", ["TOKEN", "=value", "2_TOKEN=value", "BAD-NAME=value"])
def test_parse_assignment_rejects_missing_separator_and_invalid_names(assignment):
    with pytest.raises(click.BadParameter):
        parse_assignment(assignment)


def test_read_secret_value_uses_hidden_prompt(monkeypatch, capsys):
    canary = "sdk-secret-canary-7f3a"
    prompt = monkeypatch.setattr(click, "prompt", lambda *args, **kwargs: canary)

    assert read_secret_value(False) == canary
    captured = capsys.readouterr()
    assert canary not in captured.out
    assert canary not in captured.err
    assert prompt is None


def test_read_secret_value_reads_stdin_without_echo(monkeypatch, capsys):
    canary = "sdk-secret-canary-7f3a"
    monkeypatch.setattr("sys.stdin", io.StringIO(canary + "\r\n"))

    assert read_secret_value(True) == canary
    captured = capsys.readouterr()
    assert canary not in captured.out
    assert canary not in captured.err


@pytest.mark.parametrize("value_stdin", [False, True])
def test_read_secret_value_rejects_empty_input(monkeypatch, value_stdin):
    if value_stdin:
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
    else:
        monkeypatch.setattr(click, "prompt", lambda *args, **kwargs: "")

    with pytest.raises(click.UsageError, match="Secret value cannot be empty"):
        read_secret_value(value_stdin)


def test_configuration_records_are_sorted_and_never_expose_secrets():
    canary = "sdk-secret-canary-7f3a"

    assert secret_records({"Z_TOKEN": canary, "A_TOKEN": "anything"}) == [
        {"name": "A_TOKEN", "value": "***REDACTED***"},
        {"name": "Z_TOKEN", "value": "***REDACTED***"},
    ]
    assert environment_records({"Z": "last", "A": ""}) == [
        {"name": "A", "value": ""},
        {"name": "Z", "value": "last"},
    ]
    assert deployment_environment_records([Secret("TOKEN"), Env("DEBUG", "true")]) == [
        {"name": "DEBUG", "value": "true"},
        {"from_secret": "TOKEN", "name": "TOKEN"},
    ]
