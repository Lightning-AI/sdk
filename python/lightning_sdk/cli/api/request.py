"""Raw Lightning API request command."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import requests
import rich_click as click

from lightning_sdk import __version__
from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.lightning_cloud.login import Auth

_CACHE_DIR = Path.home() / ".lightning" / "cache" / "api"
_DEFAULT_ACCEPT = "application/json"
_DEFAULT_CONTENT_TYPE = "application/json"
_DURATION_PATTERN = re.compile(r"^(?P<value>\d+)(?P<unit>[smhd]?)$")
_JSON_CONTENT_TYPES = ("application/json", "+json")
_REQUEST_TIMEOUT = 60


class _APIRequestCommand(click.Command):
    def format_usage(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        formatter.write_usage(ctx.command_path.replace(" __request", ""), " ".join(self.collect_usage_pieces(ctx)))


@dataclass
class _APIResponse:
    status_code: int
    reason: str
    headers: dict[str, str]
    content: bytes
    url: str
    http_version: str = "HTTP/1.1"

    @classmethod
    def from_requests(cls, response: requests.Response) -> _APIResponse:
        raw_version = getattr(getattr(response, "raw", None), "version", 11)
        version = "HTTP/1.0" if raw_version == 10 else "HTTP/2" if raw_version == 20 else "HTTP/1.1"
        return cls(
            status_code=response.status_code,
            reason=response.reason,
            headers=dict(response.headers),
            content=response.content,
            url=response.url,
            http_version=version,
        )


def _parse_duration(duration: str) -> int:
    match = _DURATION_PATTERN.match(duration)
    if not match:
        raise click.BadParameter('duration must look like "3600s", "60m", or "1h"')

    value = int(match.group("value"))
    unit = match.group("unit") or "s"
    return value * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def _cache_path(key_data: dict[str, Any]) -> Path:
    key = json.dumps(key_data, sort_keys=True, default=str).encode("utf-8")
    return _CACHE_DIR / f"{hashlib.sha256(key).hexdigest()}.json"


def _read_cache(path: Path, max_age_seconds: int) -> _APIResponse | None:
    if not path.exists():
        return None

    with path.open() as f:
        cached = json.load(f)

    if time.time() - cached["created_at"] > max_age_seconds:
        return None

    return _APIResponse(
        status_code=cached["status_code"],
        reason=cached["reason"],
        headers=cached["headers"],
        content=base64.b64decode(cached["content"]),
        url=cached["url"],
        http_version=cached.get("http_version", "HTTP/1.1"),
    )


def _write_cache(path: Path, response: _APIResponse) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(
            {
                "created_at": time.time(),
                "status_code": response.status_code,
                "reason": response.reason,
                "headers": response.headers,
                "content": base64.b64encode(response.content).decode("ascii"),
                "url": response.url,
                "http_version": response.http_version,
            },
            f,
        )


def _parse_header(header: str) -> tuple[str, str]:
    if ":" not in header:
        raise click.BadParameter("headers must be in key:value format")
    key, value = header.split(":", 1)
    key = key.strip()
    if not key:
        raise click.BadParameter("header name cannot be empty")
    return key, value.strip()


def _parse_key_value(item: str) -> tuple[str, str]:
    if "=" not in item:
        raise click.BadParameter("fields must be in key=value format")
    key, value = item.split("=", 1)
    if not key:
        raise click.BadParameter("field name cannot be empty")
    return key, value


def _read_field_value(value: str) -> str:
    if value == "@-":
        return sys.stdin.read()
    if value.startswith("@"):
        try:
            return Path(value[1:]).read_text()
        except OSError as ex:
            raise click.ClickException(f"failed to read field value from {value[1:]}: {ex}") from ex
    return value


def _parse_typed_value(value: str) -> Any:
    value = _read_field_value(value)
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _stringify_query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _split_nested_key(key: str) -> list[str]:
    if "[" not in key:
        return [key]

    parts: list[str] = []
    current = []
    index = 0
    while index < len(key):
        char = key[index]
        if char == "[":
            if current:
                parts.append("".join(current))
                current = []
            end = key.find("]", index)
            if end == -1:
                raise click.BadParameter(f"invalid nested field syntax: {key}")
            parts.append(key[index + 1 : end])
            index = end + 1
        else:
            current.append(char)
            index += 1
    if current:
        parts.append("".join(current))
    return parts


def _path_conflicts(container: Any, parts: list[str]) -> bool:
    if not parts:
        return False
    if isinstance(container, list):
        if not container:
            return False
        if parts[0] == "":
            return False
        return _path_conflicts(container[-1], parts)
    if not isinstance(container, dict):
        return True
    head = parts[0]
    if len(parts) == 1:
        return head in container
    if head not in container:
        return False
    return _path_conflicts(container[head], parts[1:])


def _set_nested_value(container: dict[str, Any] | list[Any], parts: list[str], value: Any) -> None:
    head = parts[0]
    if head == "":
        if not isinstance(container, list):
            raise click.BadParameter("array field syntax must follow an array key")
        if len(parts) == 1:
            container.append(value)
            return
        if not container or _path_conflicts(container[-1], parts[1:]):
            container.append([] if parts[1] == "" else {})
        _set_nested_value(container[-1], parts[1:], value)
        return

    if not isinstance(container, dict):
        raise click.BadParameter("object field syntax cannot be inserted into an array value")

    if len(parts) == 1:
        if head in container:
            existing = container[head]
            if isinstance(existing, list):
                existing.append(value)
            else:
                container[head] = [existing, value]
        else:
            container[head] = value
        return

    if head not in container or container[head] is None:
        container[head] = [] if parts[1] == "" else {}
    _set_nested_value(container[head], parts[1:], value)


def _fields_to_json(raw_fields: Iterable[str], typed_fields: Iterable[str]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for item in raw_fields:
        key, value = _parse_key_value(item)
        _set_nested_value(body, _split_nested_key(key), value)
    for item in typed_fields:
        key, value = _parse_key_value(item)
        _set_nested_value(body, _split_nested_key(key), _parse_typed_value(value))
    return body


def _fields_to_query(raw_fields: Iterable[str], typed_fields: Iterable[str]) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = []
    for item in raw_fields:
        key, value = _parse_key_value(item)
        params.append((key, value))
    for item in typed_fields:
        key, value = _parse_key_value(item)
        params.append((key, _stringify_query_value(_parse_typed_value(value))))
    return params


def _build_url(path: str, hostname: str | None) -> str:
    if path.startswith(("http://", "https://")):
        return path

    base_url = hostname or _get_cloud_url()
    if "://" not in base_url:
        base_url = f"https://{base_url}"
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _has_header(headers: dict[str, str], header_name: str) -> bool:
    return any(key.lower() == header_name.lower() for key in headers)


def _request_headers(user_headers: tuple[str, ...]) -> dict[str, str]:
    headers = dict(_parse_header(header) for header in user_headers)
    if not _has_header(headers, "authorization"):
        headers["Authorization"] = Auth().authenticate() or ""
    if not _has_header(headers, "accept"):
        headers["Accept"] = _DEFAULT_ACCEPT
    if not _has_header(headers, "user-agent"):
        headers["User-Agent"] = f"lightning-sdk/{__version__}"
    return headers


def _read_input(input_file: str | None) -> bytes | None:
    if input_file is None:
        return None
    if input_file == "-":
        return sys.stdin.buffer.read()
    try:
        return Path(input_file).read_bytes()
    except OSError as ex:
        raise click.ClickException(f"failed to read request body from {input_file}: {ex}") from ex


def _format_response_head(response: _APIResponse) -> str:
    lines = [f"{response.http_version} {response.status_code} {response.reason}".rstrip()]
    lines.extend(f"{key}: {value}" for key, value in response.headers.items())
    return "\n".join(lines)


def _is_json_response(response: _APIResponse) -> bool:
    content_type = response.headers.get("Content-Type", response.headers.get("content-type", "")).lower()
    return any(marker in content_type for marker in _JSON_CONTENT_TYPES)


def _decode_body(response: _APIResponse) -> str:
    encoding = "utf-8"
    content_type = response.headers.get("Content-Type", response.headers.get("content-type", ""))
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
    if match:
        encoding = match.group(1)
    return response.content.decode(encoding, errors="replace")


def _format_body(response: _APIResponse) -> str:
    if not response.content:
        return ""
    if _is_json_response(response):
        try:
            return json.dumps(json.loads(response.content), indent=2) + "\n"
        except json.JSONDecodeError:
            pass
    return _decode_body(response)


def _run_jq(jq_filter: str, payload: str) -> str:
    jq = shutil.which("jq")
    if jq is None:
        raise click.ClickException("`--jq` requires the `jq` executable to be installed")
    result = subprocess.run([jq, jq_filter], input=payload, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise click.ClickException(result.stderr.strip() or "`jq` failed")
    return result.stdout


def _response_output(response: _APIResponse, jq_filter: str | None) -> str:
    if jq_filter:
        return _run_jq(jq_filter, _decode_body(response))
    return _format_body(response)


def _redacted_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = dict(headers)
    for key in list(redacted):
        if key.lower() == "authorization":
            redacted[key] = "<redacted>"
    return redacted


def _cache_headers(headers: dict[str, str]) -> dict[str, str]:
    cache_headers = dict(headers)
    for key, value in list(cache_headers.items()):
        if key.lower() == "authorization":
            cache_headers[key] = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return cache_headers


def _request_target(url: str) -> str:
    parsed = urlparse(url)
    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    return target


def _echo_verbose_request(method: str, url: str, headers: dict[str, str], body: bytes | None) -> None:
    parsed = urlparse(url)
    click.echo(f"> {method} {_request_target(url)} HTTP/1.1", err=True)
    click.echo(f"> Host: {parsed.netloc}", err=True)
    for key, value in _redacted_headers(headers).items():
        click.echo(f"> {key}: {value}", err=True)
    if body:
        click.echo(">", err=True)
        click.echo(body.decode("utf-8", errors="replace"), err=True)


def _echo_verbose_response(response: _APIResponse) -> None:
    click.echo(f"< {response.http_version} {response.status_code} {response.reason}".rstrip(), err=True)
    for key, value in response.headers.items():
        click.echo(f"< {key}: {value}", err=True)


def _perform_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    params: list[tuple[str, str]],
    body: bytes | None,
    cache_duration: str | None,
    verbose: bool,
) -> _APIResponse:
    cache_file = None
    if cache_duration:
        cache_file = _cache_path(
            {
                "method": method,
                "url": url,
                "headers": _cache_headers(headers),
                "params": params,
                "body": body.decode("utf-8", errors="replace") if body else None,
            }
        )
        cached = _read_cache(cache_file, _parse_duration(cache_duration))
        if cached is not None:
            return cached

    if verbose:
        _echo_verbose_request(method, url, headers, body)

    try:
        response = requests.request(method, url, headers=headers, params=params, data=body, timeout=_REQUEST_TIMEOUT)
    except requests.RequestException as ex:
        raise click.ClickException(str(ex)) from ex

    api_response = _APIResponse.from_requests(response)
    if verbose:
        _echo_verbose_response(api_response)
    if cache_file is not None and api_response.status_code < 400:
        _write_cache(cache_file, api_response)
    return api_response


@click.command("__request", hidden=True, cls=_APIRequestCommand)
@click.argument("path")
@click.option(
    "--cache",
    "cache_duration",
    metavar="<duration>",
    help=(
        'Cache successful responses, e.g. "3600s", "60m", "1h". '
        "The cache key includes method, URL, query fields, request body, and request headers."
    ),
)
@click.option(
    "-F",
    "--field",
    "fields",
    multiple=True,
    metavar="<key=value>",
    help=(
        "Add a typed key=value field. Fields are query parameters for GET or --input requests, "
        'and JSON body fields otherwise. Use "@<path>" or "@-" to read from file or stdin.'
    ),
)
@click.option("-H", "--header", "headers", multiple=True, metavar="<key:value>", help="Add an HTTP request header.")
@click.option("--hostname", metavar="<string>", help="Lightning hostname or base URL for the request.")
@click.option("-i", "--include", is_flag=True, help="Include HTTP response status line and headers in the output.")
@click.option("--input", "input_file", metavar="<file>", help='The file to use as body; use "-" for standard input.')
@click.option("-q", "--jq", "jq_filter", metavar="<string>", help="Filter JSON response output using jq syntax.")
@click.option("-X", "--method", metavar="<string>", help='The HTTP method for the request. Defaults to "GET".')
@click.option(
    "-f",
    "--raw-field",
    "raw_fields",
    multiple=True,
    metavar="<key=value>",
    help=(
        "Add a string key=value field. Fields are query parameters for GET or --input requests, "
        "and JSON body fields otherwise."
    ),
)
@click.option("--silent", is_flag=True, help="Do not print the response body.")
@click.option("--verbose", is_flag=True, help="Include full HTTP request and response metadata.")
def api_request(
    path: str,
    cache_duration: str | None,
    fields: tuple[str, ...],
    headers: tuple[str, ...],
    hostname: str | None,
    include: bool,
    input_file: str | None,
    jq_filter: str | None,
    method: str | None,
    raw_fields: tuple[str, ...],
    silent: bool,
    verbose: bool,
) -> None:
    """Make an authenticated raw HTTP request to the Lightning API."""
    request_method = (method or ("POST" if fields or raw_fields or input_file else "GET")).upper()
    request_headers = _request_headers(headers)
    input_body = _read_input(input_file)
    params: list[tuple[str, str]] = []
    body = input_body
    body_is_json = False

    if input_body is not None or request_method == "GET":
        params = _fields_to_query(raw_fields, fields)
    elif fields or raw_fields:
        body_json = _fields_to_json(raw_fields, fields)
        body = json.dumps(body_json).encode("utf-8")
        body_is_json = True

    if body_is_json and not _has_header(request_headers, "content-type"):
        request_headers["Content-Type"] = _DEFAULT_CONTENT_TYPE

    url = _build_url(path, hostname)
    response = _perform_request(
        method=request_method,
        url=url,
        headers=request_headers,
        params=params,
        body=body,
        cache_duration=cache_duration,
        verbose=verbose,
    )

    if include:
        click.echo(_format_response_head(response))
        if not silent:
            click.echo()

    if not silent:
        output = _response_output(response, jq_filter)
        if output:
            click.echo(output, nl=not output.endswith("\n"))

    if response.status_code >= 400:
        raise click.ClickException(f"HTTP {response.status_code} {response.reason}".rstrip())
