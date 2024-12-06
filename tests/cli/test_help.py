import subprocess
from lightning_sdk.cli.entrypoint import _LIGHTNING_AVAILABLE
import pytest
import sys


def test_root_message():
    message = """NAME
    lightning - Command line interface (CLI) to interact with/manage Lightning AI Studios.

SYNOPSIS
    lightning GROUP | COMMAND

DESCRIPTION
    Command line interface (CLI) to interact with/manage Lightning AI Studios.

GROUPS
    GROUP is one of the following:

     aihub
       Interact with Lightning Studio - AI Hub.

     download
       Download files and folders from Lightning AI.

     run
       Run async workloads on the Lightning AI platform.

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

@pytest.mark.skipif(
    not _LIGHTNING_AVAILABLE,
    reason="This is the CLI if lightning is available",
)
def test_run_message_lightning_available():
    message = """NAME
    lightning run - Run async workloads on the Lightning AI platform.

SYNOPSIS
    lightning run COMMAND

DESCRIPTION
    Run async workloads on the Lightning AI platform.

COMMANDS
    COMMAND is one of the following:

     app
       Legacy CLI for `lightning_app run app`.

     job
       Run async workloads using a docker image or a compute environment from your studio.

     model
       Legacy CLI for `fabric run model`."""
    result = subprocess.run("lightning run", shell=True, capture_output=True, text=True)
    assert message in result.stdout or message in result.stderr


@pytest.mark.skipif(_LIGHTNING_AVAILABLE, reason="This is the CLI if lightning is not available")
def test_run_message_lightning_unavailable():
    message = """NAME
    lightning run - Run async workloads on the Lightning AI platform.

SYNOPSIS
    lightning run COMMAND

DESCRIPTION
    Run async workloads on the Lightning AI platform.

COMMANDS
    COMMAND is one of the following:

     job
       Run async workloads using a docker image or a compute environment from your studio."""
    result = subprocess.run("lightning run", shell=True, capture_output=True, text=True)
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

# for some reason the strings are slightly different for every python version. It doesn't make sense to list them all here
@pytest.mark.skipif(sys.version_info < (3, 10), reason="requires python3.10 or above")
def test_run_job_help():

    result = subprocess.run("lightning run job --help", shell=True, capture_output=True, text=True)
    message = """INFO: Showing help with the command 'lightning run job -- --help'.

NAME
    lightning run job - Run async workloads using a docker image or a compute environment from your studio.

SYNOPSIS
    lightning run job NAME MACHINE <flags>

DESCRIPTION
    Run async workloads using a docker image or a compute environment from your studio.

POSITIONAL ARGUMENTS
    NAME
        Type: str
        The name of the job. Needs to be unique within the teamspace.
    MACHINE
        Type: str
        The machine type to run the job on. One of CPU_SMALL, CPU, DATA_PREP, DATA_PREP_MAX, DATA_PREP_ULTRA, T4, T4_X_4, L4, L4_X_4, L4_X_8, A10G, A10G_X_4, A10G_X_8, L40S, L40S_X_4, L40S_X_8, A100_X_8, H100_X_8, H200_X_8.

FLAGS
    --command=COMMAND
        Type: Optional[Optional]
        Default: None
        The command to run inside your job. Required if using a studio. Optional if using an image. If not provided for images, will run the container entrypoint and default command.
    -s, --studio=STUDIO
        Type: Optional[Optional]
        Default: None
        The studio env to run the job with. Mutually exclusive with image.
    --image=IMAGE
        Type: Optional[Optional]
        Default: None
        The docker image to run the job with. Mutually exclusive with studio.
    -t, --teamspace=TEAMSPACE
        Type: Optional[Optional]
        Default: None
        The teamspace the job should be associated with. Defaults to the current teamspace.
    -o, --org=ORG
        Type: Optional[Optional]
        Default: None
        The organization owning the teamspace (if any). Defaults to the current organization.
    -u, --user=USER
        Type: Optional[Optional]
        Default: None
        The user owning the teamspace (if any). Defaults to the current user.
    --cluster=CLUSTER
        Type: Optional[Optional]
        Default: None
        The cluster to run the job on. Defaults to the studio cluster if running with studio compute env. If not provided will fall back to the teamspaces default cluster.
    -e, --env=ENV
        Type: Optional[Optional]
        Default: None
        Environment variables to set inside the job.
    --interruptible=INTERRUPTIBLE
        Type: bool
        Default: False
        Whether the job should run on interruptible instances. They are cheaper but can be preempted.
    --image_credentials=IMAGE_CREDENTIALS
        Type: Optional[Optional]
        Default: None
        The credentials used to pull the image. Required if the image is private. This should be the name of the respective credentials secret created on the Lightning AI platform.
    --cluster_auth=CLUSTER_AUTH
        Type: bool
        Default: False
        Whether to authenticate with the cluster to pull the image. Required if the registry is part of a cluster provider (e.g. ECR).

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS"""

    assert message in result.stderr or message in result.stdout
