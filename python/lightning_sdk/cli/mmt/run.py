"""MMT run command."""

from typing import Optional, Sequence, Union

import click

from lightning_sdk.cli.job.run import _MACHINE_VALUES, _resolve_envs, _resolve_path_mapping
from lightning_sdk.machine import Machine
from lightning_sdk.mmt import MMT
from lightning_sdk.teamspace import Teamspace


@click.command("run")
@click.option("--name", default=None, help="The name of the job. Needs to be unique within the teamspace.")
@click.option(
    "--num-machines", "--num_machines", default=2, show_default=True, help="The number of Machines to run on."
)
@click.option(
    "--machine",
    default="CPU",
    show_default=True,
    type=click.Choice(_MACHINE_VALUES),
    help="The machine type to run the job on.",
)
@click.option(
    "--command",
    default=None,
    help=(
        "The command to run inside your job. "
        "Required if using a studio. "
        "Optional if using an image. "
        "If not provided for images, will run the container entrypoint and default command."
    ),
)
@click.option(
    "--studio",
    default=None,
    help="The studio env to run the multi-machine job with. Mutually exclusive with image.",
)
@click.option(
    "--image",
    default=None,
    help="The docker image to run the multi-machine job with. Mutually exclusive with studio.",
)
@click.option(
    "--teamspace",
    default=None,
    help="The teamspace the job should be associated with. Defaults to the current teamspace.",
)
@click.option(
    "--org",
    default=None,
    help="The organization owning the teamspace (if any). Defaults to the current organization.",
)
@click.option("--user", default=None, help="The user owning the teamspace (if any). Defaults to the current user.")
@click.option(
    "--cloud-account",
    "--cloud_account",
    default=None,
    help=(
        "The cloud account to run the job on. "
        "Defaults to the studio cloud account if running with studio compute env. "
        "If not provided will fall back to the teamspaces default cloud account."
    ),
)
@click.option(
    "--env",
    "-e",
    default=[""],
    help=("Environment variable to set inside the job. Should be of format KEY=VALUE"),
    multiple=True,
)
@click.option(
    "--interruptible",
    is_flag=True,
    flag_value=True,
    default=False,
    help="Whether the job should run on interruptible instances. They are cheaper but can be preempted.",
)
@click.option(
    "--image-credentials",
    "--image_credentials",
    default=None,
    help=(
        "The credentials used to pull the image. "
        "Required if the image is private. "
        "This should be the name of the respective credentials secret created on the Lightning AI platform."
    ),
)
@click.option(
    "--cloud-account-auth",
    "--cloud_account_auth",
    is_flag=True,
    default=False,
    help=(
        "Whether to authenticate with the cloud account to pull the image. "
        "Required if the registry is part of a cloud provider (e.g. ECR)."
    ),
)
@click.option(
    "--entrypoint",
    default=None,
    show_default=True,
    help=(
        "The entrypoint of your docker container. "
        "Default runs the provided command in a standard shell. "
        "To use the pre-defined entrypoint of the provided image, set this to an empty string. "
        "Only applicable when submitting docker jobs."
    ),
)
@click.option(
    "--path-mapping",
    "--path_mapping",
    default=[""],
    help=(
        "Maps path inside of containers to paths inside data-connections. "
        "Should be of form <CONTAINER_PATH_1>:<CONNECTION_NAME_1>:<PATH_WITHIN_CONNECTION_1> and "
        "omitting the path inside the connection defaults to the connections root. "
        "Can be specified multiple times for multiple mappings"
    ),
    multiple=True,
)
@click.option(
    "--path-mappings",
    "--path_mappings",
    default="",
    help=(
        "Maps path inside of containers to paths inside data-connections. "
        "Should be a comma separated list of form: "
        "<MAPPING_1>,<MAPPING_2>,... "
        "where each mapping is of the form "
        "<CONTAINER_PATH_1>:<CONNECTION_NAME_1>:<PATH_WITHIN_CONNECTION_1> and "
        "omitting the path inside the connection defaults to the connections root. "
        "Instead of a comma-separated list, consider passing --path-mapping multiple times."
    ),
)
def run_mmt(
    name: Optional[str] = None,
    num_machines: int = 2,
    machine: str = "CPU",
    command: Optional[str] = None,
    studio: Optional[str] = None,
    image: Optional[str] = None,
    teamspace: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None,
    cloud_account: Optional[str] = None,
    env: Sequence[str] = (),
    interruptible: bool = False,
    image_credentials: Optional[str] = None,
    cloud_account_auth: bool = False,
    entrypoint: str = "sh -c",
    path_mapping: Sequence[str] = (),
    path_mappings: str = "",
    artifacts_local: Optional[str] = None,
    artifacts_remote: Optional[str] = None,
) -> None:
    """Run async workloads on multiple machines using a docker image."""
    if name is None:
        from datetime import datetime

        timestr = datetime.now().strftime("%b-%d-%H_%M")
        name = f"mmt-{timestr}"

    try:
        machine_enum: Union[str, Machine] = getattr(Machine, machine.upper(), Machine(machine, machine))
    except KeyError:
        machine_enum = machine

    resolved_teamspace = Teamspace(name=teamspace, org=org, user=user)
    path_mappings_dict = _resolve_path_mapping(path_mappings=path_mappings)
    for mapping in path_mapping:
        path_mappings_dict.update(_resolve_path_mapping(path_mappings=mapping))

    env_dict = {}
    for value in env:
        env_dict.update(_resolve_envs(value))

    MMT.run(
        name=name,
        num_machines=num_machines,
        machine=machine_enum,
        command=command,
        studio=studio,
        image=image,
        teamspace=resolved_teamspace,
        org=org,
        user=user,
        cloud_account=cloud_account,
        env=env_dict,
        interruptible=interruptible,
        image_credentials=image_credentials,
        cloud_account_auth=cloud_account_auth,
        entrypoint=entrypoint,
        path_mappings=path_mappings_dict,
        artifacts_local=artifacts_local,
        artifacts_remote=artifacts_remote,
    )
