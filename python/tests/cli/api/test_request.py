from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli
from tests.cli.help import mock_command_logging


def _response(
    content: bytes = b'{"ok": true}',
    *,
    status_code: int = 200,
    reason: str = "OK",
    headers: dict[str, str] | None = None,
    url: str = "https://lightning.test/v1/test",
) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.reason = reason
    response._content = content
    response.headers.update(headers or {"Content-Type": "application/json"})
    response.url = url
    response.raw = SimpleNamespace(version=11)
    return response


def _run(args: list[str], **kwargs):
    runner = CliRunner()
    return runner.invoke(main_cli, args, prog_name="lightning", catch_exceptions=False, **kwargs)


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_get_uses_configured_url_and_auth(mock_request, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Bearer test-token"
    mock_request.return_value = _response(url="https://lightning.test/v1/me")

    result = _run(["api", "/v1/me"])

    assert result.exit_code == 0
    assert '"ok": true' in result.output
    mock_request.assert_called_once()
    mock_auth.assert_called_once_with()
    mock_auth.return_value.authenticate.assert_called_once_with()
    assert mock_request.call_args.args[:2] == ("GET", "https://lightning.test/v1/me")
    headers = mock_request.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["Accept"] == "application/json"
    assert headers["User-Agent"].startswith("lightning-sdk/")


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_preserves_explicit_authorization_header(mock_request, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_request.return_value = _response(url="https://lightning.test/v1/me")

    result = _run(["api", "/v1/me", "-H", "Authorization: Bearer override-token"])

    assert result.exit_code == 0
    mock_auth.assert_not_called()
    assert mock_request.call_args.kwargs["headers"]["Authorization"] == "Bearer override-token"


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_accepts_options_before_path(mock_request, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response(url="https://lightning.test/v1/me")

    result = _run(["api", "-X", "GET", "-H", "Accept: application/json", "/v1/me"])

    assert result.exit_code == 0
    assert mock_request.call_args.args[:2] == ("GET", "https://lightning.test/v1/me")
    assert mock_request.call_args.kwargs["headers"]["Accept"] == "application/json"


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_accepts_versioned_relative_path(mock_request, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response(url="https://lightning.test/v1/me")

    result = _run(["api", "v1/me"])

    assert result.exit_code == 0
    assert mock_request.call_args.args[:2] == ("GET", "https://lightning.test/v1/me")


@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_fallback_ignores_option_values_with_slashes(mock_request) -> None:
    result = _run(["api", "missing", "-H", "Accept: application/json"])

    assert result.exit_code != 0
    assert "No such command 'missing'" in result.output
    mock_request.assert_not_called()


@mock_command_logging
def test_api_group_is_hidden_from_top_level_help() -> None:
    result = _run(["--help"])

    assert result.exit_code == 0
    assert "\n  api " not in result.output


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_posts_json_fields(mock_request, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response()

    result = _run(
        [
            "api",
            "/v1/test",
            "-f",
            "name=example",
            "-F",
            "count=3",
            "-F",
            "enabled=true",
        ]
    )

    assert result.exit_code == 0
    assert mock_request.call_args.args[0] == "POST"
    assert mock_request.call_args.kwargs["headers"]["Content-Type"] == "application/json"
    assert mock_request.call_args.kwargs["data"] == b'{"name": "example", "count": 3, "enabled": true}'


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_accepts_long_field_header_and_method_options(mock_request, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response()

    result = _run(
        [
            "api",
            "/v1/test",
            "--method",
            "PATCH",
            "--header",
            "X-Test: yes",
            "--raw-field",
            "name=example",
            "--field",
            "count=3",
        ]
    )

    assert result.exit_code == 0
    assert mock_request.call_args.args[:2] == ("PATCH", "https://lightning.test/v1/test")
    assert mock_request.call_args.kwargs["headers"]["X-Test"] == "yes"
    assert mock_request.call_args.kwargs["data"] == b'{"name": "example", "count": 3}'


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_input_body_does_not_default_content_type(mock_request, mock_auth, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response()
    body_file = tmp_path / "payload.txt"
    body_file.write_text("plain text")

    result = _run(["api", "/v1/upload", "-X", "POST", "--input", str(body_file)])

    assert result.exit_code == 0
    headers = mock_request.call_args.kwargs["headers"]
    assert "Content-Type" not in headers
    assert mock_request.call_args.kwargs["data"] == b"plain text"


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_input_body_from_stdin(mock_request, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response()

    result = _run(["api", "/v1/upload", "-X", "POST", "--input", "-"], input=b"stdin body")

    assert result.exit_code == 0
    assert mock_request.call_args.kwargs["data"] == b"stdin body"


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_adds_fields_to_get_query(mock_request, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response()

    result = _run(["api", "/v1/search", "-X", "GET", "-f", "q=repo:foo", "-F", "limit=10"])

    assert result.exit_code == 0
    assert mock_request.call_args.args[0] == "GET"
    assert mock_request.call_args.kwargs["params"] == [("q", "repo:foo"), ("limit", "10")]
    assert mock_request.call_args.kwargs["data"] is None


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_uses_hostname_base_url(mock_request, mock_auth) -> None:
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response(url="https://api.lightning.test/base/v1/test")

    result = _run(["api", "/v1/test", "--hostname", "https://api.lightning.test/base"])

    assert result.exit_code == 0
    assert mock_request.call_args.args[:2] == ("GET", "https://api.lightning.test/base/v1/test")


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_supports_nested_array_fields(mock_request, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response()

    result = _run(
        [
            "api",
            "/v1/orgs/example/properties/schema",
            "-X",
            "PATCH",
            "-F",
            "properties[][property_name]=environment",
            "-F",
            "properties[][default_value]=production",
            "-F",
            "properties[][allowed_values][]=staging",
            "-F",
            "properties[][allowed_values][]=production",
        ]
    )

    assert result.exit_code == 0
    assert mock_request.call_args.kwargs["data"] == (
        b'{"properties": [{"property_name": "environment", "default_value": "production", '
        b'"allowed_values": ["staging", "production"]}]}'
    )


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request._run_jq")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_filters_with_jq(mock_request, mock_jq, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response(b'{"title": "hello"}')
    mock_jq.return_value = "hello\n"

    result = _run(["api", "/v1/test", "--jq", ".title"])

    assert result.output == "hello\n"
    mock_jq.assert_called_once_with(".title", '{"title": "hello"}')


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request._run_jq")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_filters_with_short_jq_option(mock_request, mock_jq, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response(b'{"title": "hello"}')
    mock_jq.return_value = "hello\n"

    result = _run(["api", "/v1/test", "-q", ".title"])

    assert result.output == "hello\n"
    mock_jq.assert_called_once_with(".title", '{"title": "hello"}')


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_include_outputs_response_head(mock_request, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response(
        b'{"created": true}',
        status_code=201,
        reason="Created",
        headers={"Content-Type": "application/json", "X-Request-Id": "abc"},
    )

    result = _run(["api", "/v1/test", "--include"])

    assert result.exit_code == 0
    assert "HTTP/1.1 201 Created" in result.output
    assert "X-Request-Id: abc" in result.output
    assert '"created": true' in result.output


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_silent_suppresses_response_body(mock_request, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response(b'{"hidden": true}')

    result = _run(["api", "/v1/test", "--silent"])

    assert result.exit_code == 0
    assert result.output == ""


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_verbose_outputs_redacted_request_and_response(mock_request, mock_auth, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    mock_auth.return_value.authenticate.return_value = "Bearer secret-token"
    mock_request.return_value = _response()

    result = _run(["api", "/v1/test", "--verbose", "--silent"])

    assert result.exit_code == 0
    assert "> GET /v1/test HTTP/1.1" in result.stderr
    assert "> Authorization: <redacted>" in result.stderr
    assert "secret-token" not in result.stderr
    assert "< HTTP/1.1 200 OK" in result.stderr


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_cache_reuses_successful_response(mock_request, mock_auth, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    monkeypatch.setattr("lightning_sdk.cli.api.request._CACHE_DIR", tmp_path)
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.return_value = _response(b'{"cached": true}')

    first = _run(["api", "/v1/test", "--cache", "1h"])
    second = _run(["api", "/v1/test", "--cache", "1h"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert '"cached": true' in second.output
    mock_request.assert_called_once()


@patch("lightning_sdk.cli.api.request.Auth")
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_does_not_cache_http_errors(mock_request, mock_auth, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://lightning.test")
    monkeypatch.setattr("lightning_sdk.cli.api.request._CACHE_DIR", tmp_path)
    mock_auth.return_value.authenticate.return_value = "Basic token"
    mock_request.side_effect = [
        _response(b'{"error": "temporary"}', status_code=500, reason="Internal Server Error"),
        _response(b'{"ok": true}'),
    ]

    first = _run(["api", "/v1/test", "--cache", "1h"])
    second = _run(["api", "/v1/test", "--cache", "1h"])

    assert first.exit_code != 0
    assert second.exit_code == 0
    assert mock_request.call_count == 2


@pytest.mark.parametrize(
    ("args", "option"),
    [
        (["--paginate"], "--paginate"),
        (["--slurp"], "--slurp"),
        (["--preview", "foo"], "--preview"),
        (["--template", "{{.name}}"], "--template"),
    ],
)
@patch("lightning_sdk.cli.api.request.requests.request")
@mock_command_logging
def test_api_request_rejects_removed_unsupported_options(mock_request, args, option) -> None:
    result = _run(["api", "/v1/test", *args])

    assert result.exit_code != 0
    assert f"No such option '{option}'" in result.output
    mock_request.assert_not_called()
