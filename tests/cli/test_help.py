import subprocess
from lightning_sdk.cli.entrypoint import _LIGHTNING_AVAILABLE
import pytest
import sys


@pytest.mark.skipif(
    not _LIGHTNING_AVAILABLE,
    reason="This is the CLI if lightning is available",
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

     download
       Download files and folders from Lightning AI.

     run
       Legacy CLI for `fabric run model` and `lightning run app`.

     upload
       Upload files and folders to Lightning AI.

COMMANDS
    COMMAND is one of the following:

     login
       Login to Lightning AI Studios.

     logout
       Logout from Lightning AI Studios."""
    result = subprocess.run("lightning", shell=True, capture_output=True, text=True)
    assert message in result.stdout or message in result.stderr


@pytest.mark.skipif(_LIGHTNING_AVAILABLE, reason="This is the CLI if lightning is not available")
def test_root_message_lightning_unavailable():
    message = """NAME
    lightning - Command line interface (CLI) to interact with/manage Lightning AI Studios.

SYNOPSIS
    lightning GROUP | COMMAND

DESCRIPTION
    Command line interface (CLI) to interact with/manage Lightning AI Studios.

GROUPS
    GROUP is one of the following:

     download
       Download files and folders from Lightning AI.

     upload
       Upload files and folders to Lightning AI.

COMMANDS
    COMMAND is one of the following:

     login
       Login to Lightning AI Studios.

     logout
       Logout from Lightning AI Studios."""
    result = subprocess.run("lightning", shell=True, capture_output=True, text=True)
    assert message in result.stdout or message in result.stderr


def test_upload():
    result = subprocess.run("lightning upload file", shell=True, capture_output=True, text=True)

    message = "The function received no value for the required argument: path"
    assert message in result.stderr or message in result.stdout


@pytest.mark.skipif(
    not _LIGHTNING_AVAILABLE,
    reason="lightning run model is only available if lightning is installed",
)
@pytest.mark.skipif(sys.version_info > (3, 8), reason="requires python3.8 or below")
def test_run_model_help_py_38_and_below():
    result = subprocess.run("lightning run model --help", shell=True, capture_output=True, text=True)

    message = """NAME
    lightning run model - Legacy CLI for `fabric run model`.

SYNOPSIS
    lightning run model SCRIPT <flags> [SCRIPT_ARGS]...

DESCRIPTION
    Legacy CLI for `fabric run model`.

POSITIONAL ARGUMENTS
    SCRIPT
        Type: str
        The script containing the fabric definition to launch
    SCRIPT_ARGS
        Type: typing.Any
        Arguments passed to the script to execute

FLAGS
    -a, --accelerator=ACCELERATOR
        Type: Optional[typing.Unio...
        Default: None
        The hardware accelerator to run on.
    -s, --strategy=STRATEGY
        Type: Optional[typing.Unio...
        Default: None
        Strategy for how to run across multiple devices.
    -d, --devices=DEVICES
        Type: str
        Default: '1'
        Number of devices to run on (``int``), which devices to run on (``list`` or ``str``), or ``'auto'``. The value applies per node.
    --num_nodes=NUM_NODES
        Type: int
        Default: 1
        Number of machines (nodes) for distributed execution."""

    assert message in result.stderr or message in result.stdout


@pytest.mark.skipif(
    not _LIGHTNING_AVAILABLE,
    reason="lightning run model is only available if lightning is installed",
)
@pytest.mark.skipif(sys.version_info != (3, 9), reason="requires python3.9")
def test_run_model_help_py_39():
    result = subprocess.run("lightning run model --help", shell=True, capture_output=True, text=True)

    message = """NAME
    lightning run model - Legacy CLI for `fabric run model`.

SYNOPSIS
    lightning run model SCRIPT <flags> [SCRIPT_ARGS]...

DESCRIPTION
    Legacy CLI for `fabric run model`.

POSITIONAL ARGUMENTS
    SCRIPT
        Type: str
        The script containing the fabric definition to launch
    SCRIPT_ARGS
        Type: typing.Any
        Arguments passed to the script to execute

FLAGS
    -a, --accelerator=ACCELERATOR
        Type: Optional[typing.Optional[str]]
        Default: None
        The hardware accelerator to run on.
    -s, --strategy=STRATEGY
        Type: Optional[typing.Optional[str]]
        Default: None
        Strategy for how to run across multiple devices.
    -d, --devices=DEVICES
        Type: str
        Default: '1'
        Number of devices to run on (``int``), which devices to run on (``list`` or ``str``), or ``'auto'``. The value applies per node.
    --num_nodes=NUM_NODES
        Type: int
        Default: 1
        Number of machines (nodes) for distributed execution."""

    assert message in result.stderr or message in result.stdout


@pytest.mark.skipif(
    not _LIGHTNING_AVAILABLE,
    reason="lightning run model is only available if lightning is installed",
)
@pytest.mark.skipif(sys.version_info < (3, 10), reason="requires python3.10 or above")
def test_run_model_help_py_310_and_above():
    result = subprocess.run("lightning run model --help", shell=True, capture_output=True, text=True)

    message = """NAME
    lightning run model - Legacy CLI for `fabric run model`.

SYNOPSIS
    lightning run model SCRIPT <flags> [SCRIPT_ARGS]...

DESCRIPTION
    Legacy CLI for `fabric run model`.

POSITIONAL ARGUMENTS
    SCRIPT
        Type: str
        The script containing the fabric definition to launch
    SCRIPT_ARGS
        Type: Any
        Arguments passed to the script to execute

FLAGS
    -a, --accelerator=ACCELERATOR
        Type: Optional[Optional]
        Default: None
        The hardware accelerator to run on.
    -s, --strategy=STRATEGY
        Type: Optional[Optional]
        Default: None
        Strategy for how to run across multiple devices.
    -d, --devices=DEVICES
        Type: str
        Default: '1'
        Number of devices to run on (``int``), which devices to run on (``list`` or ``str``), or ``'auto'``. The value applies per node.
    --num_nodes=NUM_NODES
        Type: int
        Default: 1
        Number of machines (nodes) for distributed execution."""

    assert message in result.stderr or message in result.stdout


@pytest.mark.skipif(
    not _LIGHTNING_AVAILABLE,
    reason="lightning run app is only available if lightning[app] is installed",
)
def test_run_app_help():
    result = subprocess.run("lightning run app --help", shell=True, capture_output=True, text=True)

    message = """INFO: Showing help with the command 'lightning run app -- --help'.

NAME
    lightning run app - Legacy CLI for `lightning_app run app`.

SYNOPSIS
    lightning run app FILE <flags>

DESCRIPTION
    Legacy CLI for `lightning_app run app`.

POSITIONAL ARGUMENTS
    FILE
        Type: str
        The file containing your application

FLAGS
    -c, --cloud=CLOUD
        Type: bool
        Default: False
        Run the app in the cloud
    --name=NAME
        Type: str
        Default: ''
        The current application name
    -w, --without_server=WITHOUT_SERVER
        Type: bool
        Default: False
        Run without server
    --no_cache=NO_CACHE
        Type: bool
        Default: False
        Disable caching of packages installed from requirements.txt
    -b, --blocking=BLOCKING
        Type: bool"""

    assert message in result.stderr or message in result.stdout
