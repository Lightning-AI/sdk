"""Vend short-lived data connection credentials to AWS-compatible tooling."""

import json
from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace, teamspace_option
from lightning_sdk.data_connection import BucketCredentials


def _profile_stanza(name: str, credentials: BucketCredentials, command: str) -> str:
    """Render an AWS config profile that refreshes itself by re-running this command."""
    lines = [f"[profile {name}]", f"credential_process = {command}"]

    # Without these two the tool resolves its own, and inside a Studio that can mean the
    # Lightning Storage endpoint — an AWS request sent to Cloudflare, rejected as
    # InvalidAccessKeyId. credential_process has nowhere to carry them, so they belong
    # on the profile.
    if credentials.region:
        lines.append(f"region = {credentials.region}")
    if credentials.endpoint:
        lines.append(f"endpoint_url = {credentials.endpoint}")

    return "\n".join(lines)


@click.command("credentials", cls=LightningCommand)
@click.argument("connection")
@teamspace_option
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["credential-process", "profile"]),
    default="credential-process",
    help=(
        "credential-process emits the JSON AWS tools expect from a credential_process "
        "command. profile emits an ~/.aws/config stanza that calls this command to refresh."
    ),
)
def connection_credentials(
    connection: str,
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    output_format: str = "credential-process",
) -> None:
    """Print short-lived credentials for a data connection's bucket.

    These credentials expire, usually within the hour. Rather than refreshing them
    yourself, wire this command into an AWS profile as a credential_process and let the
    tool re-run it on expiry - the AWS CLI, boto3, rclone, s5cmd and the Go SDK all
    understand that setting.

    Setup:
      lightning connection credentials my-bucket --format profile >> ~/.aws/config

    Then use it:
      aws s3 ls s3://my-bucket --profile my-bucket
    """
    resolved_teamspace = resolve_teamspace(teamspace=teamspace, org=org, user=user)

    try:
        credentials = resolved_teamspace.bucket_credentials(connection)
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    if output_format == "profile":
        qualified = f"{resolved_teamspace.owner.name}/{resolved_teamspace.name}"
        command = f"lightning connection credentials {connection} --teamspace {qualified}"
        click.echo(_profile_stanza(connection, credentials, command))
        return

    click.echo(json.dumps(credentials.to_credential_process()))
