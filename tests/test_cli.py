import subprocess
from lightning_sdk.cli.entrypoint import _FABRIC_AVAILABLE, _LIGHTNING_AVAILABLE
import pytest


@pytest.mark.skipif(
    not _FABRIC_AVAILABLE and not _LIGHTNING_AVAILABLE,
    reason="This is the CLI if either lightning of fabric are available",
)
def test_root_message_lightning_available():
    message = """NAME
    lightning - Command line interface (CLI) to interact with/manage Lightning AI Studios.

SYNOPSIS
    lightning GROUP | COMMAND

DESCRIPTION
    Command line interface (CLI) to interact with/manage Lightning AI Studios.

GROUPS
    GROUP is one of the following:

     run
       Legacy CLI for `fabric run model`.

COMMANDS
    COMMAND is one of the following:

     login
       Login to Lightning AI Studios.

     logout
       Logout from Lightning AI Studios.

     upload
       Upload a file or folder to a studio."""
    result = subprocess.run("lightning", shell=True, capture_output=True, text=True)
    assert message in result.stdout or message in result.stderr


@pytest.mark.skipif(
    _LIGHTNING_AVAILABLE or _FABRIC_AVAILABLE, reason="This is the CLI if neither lightning of fabric are available"
)
def test_root_message_lightning_unavailable():
    message = """NAME
    lightning - Command line interface (CLI) to interact with/manage Lightning AI Studios.

SYNOPSIS
    lightning COMMAND

DESCRIPTION
    Command line interface (CLI) to interact with/manage Lightning AI Studios.

COMMANDS
    COMMAND is one of the following:

     login
       Login to Lightning AI Studios.

     logout
       Logout from Lightning AI Studios.

     upload
       Upload a file or folder to a studio."""
    result = subprocess.run("lightning", shell=True, capture_output=True, text=True)
    assert message in result.stdout or message in result.stderr


def test_upload():
    result = subprocess.run("lightning upload", shell=True, capture_output=True, text=True)

    message = "The function received no value for the required argument: path"
    assert message in result.stderr or message in result.stdout
