"""Warning-acknowledgment helpers for ``deployment create --model`` (BYOM)."""

from typing import Any, Callable, List

import click

from lightning_sdk.lightning_cloud.openapi.rest import ApiException

_UNACKED_PREFIX = "unacknowledged BYOM warnings:"


def extract_unacked_warnings(exc: ApiException) -> List[str]:
    """Return the BYOM warning codes from an unacknowledged-warnings rejection.

    The server reports unacked warnings as a flat ``InvalidArgument`` message of the
    form ``unacknowledged BYOM warnings: CODE, CODE``. Hard errors use a different
    format and never carry this prefix, so they yield an empty list (not ackable).
    """
    text = str(exc)
    idx = text.find(_UNACKED_PREFIX)
    if idx == -1:
        return []
    tail = text[idx + len(_UNACKED_PREFIX) :]
    for sep in ('"', "\n", "\\n"):
        tail = tail.split(sep)[0]
    return [code.strip() for code in tail.split(",") if code.strip()]


def resolve_acknowledgements(codes: List[str], *, force: bool, interactive: bool) -> List[str]:
    """Decide which warning codes to acknowledge. An empty result means 'do not proceed'.

    ``force`` acknowledges everything; in interactive mode the user is prompted; in a
    non-interactive session without ``force`` nothing is acknowledged (the caller errors).
    """
    if force:
        return list(codes)
    if not interactive:
        return []
    click.echo("Deployment validation produced warnings:", err=True)
    for code in codes:
        click.echo(f"  ⚠ {code}", err=True)
    if click.confirm("Acknowledge these warnings and deploy anyway?", default=False):
        return list(codes)
    return []


def create_with_acknowledgement(
    create_fn: Callable[[List[str]], Any],
    *,
    acks: List[str],
    force: bool,
    interactive: bool,
) -> Any:
    """Run ``create_fn(acknowledged)``, retrying on unacknowledged-warning rejections.

    ``create_fn`` takes the list of acknowledged codes and performs the create, raising
    ``ApiException`` on rejection. Returns ``create_fn``'s result on success. Raises
    ``click.UsageError`` when warnings remain unacknowledged (non-interactive without
    ``--force``, or the user declined), and re-raises any non-warning error unchanged.
    """
    acknowledged = list(acks)
    while True:
        try:
            return create_fn(acknowledged)
        except ApiException as exc:
            codes = extract_unacked_warnings(exc)
            if not codes:
                raise
            newly = resolve_acknowledgements(codes, force=force, interactive=interactive)
            pending = [code for code in newly if code not in acknowledged]
            if not pending:
                raise click.UsageError(
                    "Deployment has unacknowledged warnings: "
                    + ", ".join(codes)
                    + ". Re-run with --ack <code> (repeatable) or --force."
                ) from None
            acknowledged = acknowledged + pending
