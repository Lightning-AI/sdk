import json
from datetime import datetime, timezone
from unittest import mock

import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli.connection.credentials import connection_credentials
from lightning_sdk.data_connection import BucketCredentials
from tests.cli.help import assert_help_contains, mock_command_logging


def _run(credentials, *args):
    """Invoke the command against a teamspace that returns the given credentials."""
    teamspace = mock.MagicMock()
    teamspace.name = "my-teamspace"
    teamspace.owner.name = "my-org"
    teamspace.bucket_credentials.return_value = credentials

    with mock.patch(
        "lightning_sdk.cli.connection.credentials.resolve_teamspace",
        return_value=teamspace,
    ):
        return CliRunner().invoke(connection_credentials, list(args)), teamspace


@mock_command_logging
def test_credentials_help():
    assert_help_contains(
        "lightning connection credentials --help",
        "Usage: lightning connection credentials [OPTIONS] CONNECTION",
        "Print short-lived credentials for a data connection's bucket.",
        "--teamspace",
        "--format",
    )


def test_emits_the_json_envelope_aws_reads_from_a_credential_process():
    credentials = BucketCredentials(
        access_key_id="AKIA",
        secret_access_key="secret",
        session_token="token",
        expires_at=datetime(2026, 9, 9, 22, 0, tzinfo=timezone.utc),
        region="us-west-2",
        endpoint="https://s3.us-west-2.amazonaws.com",
    )

    result, teamspace = _run(credentials, "training-data")

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "Version": 1,
        "AccessKeyId": "AKIA",
        "SecretAccessKey": "secret",
        "SessionToken": "token",
        "Expiration": "2026-09-09T22:00:00+00:00",
    }
    teamspace.bucket_credentials.assert_called_once_with("training-data")


def test_output_is_json_and_nothing_else():
    """AWS parses stdout as JSON, so a stray banner or log line would break the tool."""
    credentials = BucketCredentials(access_key_id="AKIA", secret_access_key="secret")

    result, _ = _run(credentials, "training-data")

    json.loads(result.output)


def test_profile_format_carries_region_and_endpoint_that_the_envelope_cannot():
    credentials = BucketCredentials(
        access_key_id="AKIA",
        secret_access_key="secret",
        region="us-west-2",
        endpoint="https://s3.us-west-2.amazonaws.com",
    )

    result, _ = _run(credentials, "training-data", "--format", "profile")

    assert result.exit_code == 0
    assert "[profile training-data]" in result.output
    assert (
        "credential_process = lightning connection credentials training-data --teamspace my-org/my-teamspace"
        in result.output
    )
    assert "region = us-west-2" in result.output
    assert "endpoint_url = https://s3.us-west-2.amazonaws.com" in result.output


def test_profile_omits_settings_the_connection_did_not_report():
    credentials = BucketCredentials(access_key_id="AKIA", secret_access_key="secret")

    result, _ = _run(credentials, "training-data", "--format", "profile")

    assert "region =" not in result.output
    assert "endpoint_url =" not in result.output


def test_an_unknown_connection_name_fails_with_the_lookup_error():
    teamspace = mock.MagicMock()
    teamspace.bucket_credentials.side_effect = ValueError("No data connection named 'nope' in this teamspace.")

    with mock.patch(
        "lightning_sdk.cli.connection.credentials.resolve_teamspace",
        return_value=teamspace,
    ):
        result = CliRunner().invoke(connection_credentials, ["nope"])

    assert result.exit_code != 0
    assert "No data connection named 'nope'" in result.output


def test_an_unresolvable_teamspace_says_which_flag_to_pass():
    """The shared resolver owns this message, so the command just has to not swallow it."""
    with mock.patch(
        "lightning_sdk.cli.connection.credentials.resolve_teamspace",
        side_effect=click.UsageError("Could not resolve a teamspace. Pass --teamspace OWNER/TEAMSPACE."),
    ):
        result = CliRunner().invoke(connection_credentials, ["training-data"])

    assert result.exit_code != 0
    assert "--teamspace" in result.output
