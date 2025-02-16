import subprocess
from typing import Dict

import pytest

from lightning_sdk.cli.run import _resolve_path_mapping


def test_run_help():
    result = subprocess.run("lightning run --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning run [OPTIONS] COMMAND [ARGS]...

  Run async workloads on the Lightning AI platform.

Options:
  --help  Show this message and exit.

Commands:
  job  Run async workloads using a docker image or studio.
  mmt  Run async workloads on multiple machines using a docker image.
"""
    )


def test_job_help():
    result = subprocess.run("lightning run job --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning run job [OPTIONS]

  Run async workloads using a docker image or studio.

Options:
  --name TEXT                     The name of the job. Needs to be unique
                                  within the teamspace.
  --machine [CPU_SMALL|CPU|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4|T4_X_4|L4|L4_X_4|L4_X_8|A10G|A10G_X_4|A10G_X_8|L40S|L40S_X_4|L40S_X_8|A100_X_8|H100_X_8|H200_X_8]
                                  The machine type to run the job on.
                                  [default: CPU]
  --command TEXT                  The command to run inside your job. Required
                                  if using a studio. Optional if using an
                                  image. If not provided for images, will run
                                  the container entrypoint and default
                                  command.
  --studio TEXT                   The studio env to run the job with. Mutually
                                  exclusive with image.
  --image TEXT                    The docker image to run the job with.
                                  Mutually exclusive with studio.
  --teamspace TEXT                The teamspace the job should be associated
                                  with. Defaults to the current teamspace.
  --org TEXT                      The organization owning the teamspace (if
                                  any). Defaults to the current organization.
  --user TEXT                     The user owning the teamspace (if any).
                                  Defaults to the current user.
  --cloud-account, --cloud_account TEXT
                                  The cloud account to run the job on.
                                  Defaults to the studio cloud account if
                                  running with studio compute env. If not
                                  provided will fall back to the teamspaces
                                  default cloud account.
  --env TEXT                      Environment variables to set inside the job.
  --interruptible                 Whether the job should run on interruptible
                                  instances. They are cheaper but can be
                                  preempted.
  --image-credentials, --image_credentials TEXT
                                  The credentials used to pull the image.
                                  Required if the image is private. This
                                  should be the name of the respective
                                  credentials secret created on the Lightning
                                  AI platform.
  --cloud-account-auth, --cloud_account_auth
                                  Whether to authenticate with the cloud
                                  account to pull the image. Required if the
                                  registry is part of a cloud provider (e.g.
                                  ECR).
  --entrypoint TEXT               The entrypoint of your docker container.
                                  Default runs the provided command in a
                                  standard shell. To use the pre-defined
                                  entrypoint of the provided image, set this
                                  to an empty string. Only applicable when
                                  submitting docker jobs.  [default: sh -c]
  --path-mapping, --path_mapping TEXT
                                  Maps path inside of containers to paths
                                  inside data-connections. Should be of form <
                                  CONTAINER_PATH_1>:<CONNECTION_NAME_1>:<PATH_
                                  WITHIN_CONNECTION_1> and omitting the path
                                  inside the connection defaults to the
                                  connections root. Can be specified multiple
                                  times for multiple mappings
  --path-mappings, --path_mappings TEXT
                                  Maps path inside of containers to paths
                                  inside data-connections. Should be a comma
                                  separated list of form:
                                  <MAPPING_1>,<MAPPING_2>,... where each
                                  mapping is of the form <CONTAINER_PATH_1>:<C
                                  ONNECTION_NAME_1>:<PATH_WITHIN_CONNECTION_1>
                                  and omitting the path inside the connection
                                  defaults to the connections root. Instead of
                                  a comma-separated list, consider passing
                                  --path-mapping multiple times.
  --help                          Show this message and exit.
"""  # noqa: E501
    )


def test_mmt_help():
    result = subprocess.run("lightning run mmt --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning run mmt [OPTIONS]

  Run async workloads on multiple machines using a docker image.

Options:
  --name TEXT                     The name of the job. Needs to be unique
                                  within the teamspace.
  --num-machines, --num_machines INTEGER
                                  The number of Machines to run on.  [default:
                                  2]
  --machine [CPU_SMALL|CPU|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4|T4_X_4|L4|L4_X_4|L4_X_8|A10G|A10G_X_4|A10G_X_8|L40S|L40S_X_4|L40S_X_8|A100_X_8|H100_X_8|H200_X_8]
                                  The machine type to run the job on.
                                  [default: CPU]
  --command TEXT                  The command to run inside your job. Required
                                  if using a studio. Optional if using an
                                  image. If not provided for images, will run
                                  the container entrypoint and default
                                  command.
  --studio TEXT                   The studio env to run the job with. Mutually
                                  exclusive with image.
  --image TEXT                    The docker image to run the job with.
                                  Mutually exclusive with studio.
  --teamspace TEXT                The teamspace the job should be associated
                                  with. Defaults to the current teamspace.
  --org TEXT                      The organization owning the teamspace (if
                                  any). Defaults to the current organization.
  --user TEXT                     The user owning the teamspace (if any).
                                  Defaults to the current user.
  --cloud-account, --cloud_account TEXT
                                  The cloud account to run the job on.
                                  Defaults to the studio cloud account if
                                  running with studio compute env. If not
                                  provided will fall back to the teamspaces
                                  default cloud account.
  --env TEXT                      Environment variables to set inside the job.
  --interruptible                 Whether the job should run on interruptible
                                  instances. They are cheaper but can be
                                  preempted.
  --image-credentials, --image_credentials TEXT
                                  The credentials used to pull the image.
                                  Required if the image is private. This
                                  should be the name of the respective
                                  credentials secret created on the Lightning
                                  AI platform.
  --cloud-account-auth, --cloud_account_auth
                                  Whether to authenticate with the cloud
                                  account to pull the image. Required if the
                                  registry is part of a cloud provider (e.g.
                                  ECR).
  --entrypoint TEXT               The entrypoint of your docker container.
                                  Default runs the provided command in a
                                  standard shell. To use the pre-defined
                                  entrypoint of the provided image, set this
                                  to an empty string. Only applicable when
                                  submitting docker jobs.  [default: sh -c]
  --path-mapping, --path_mapping TEXT
                                  Maps path inside of containers to paths
                                  inside data-connections. Should be of form <
                                  CONTAINER_PATH_1>:<CONNECTION_NAME_1>:<PATH_
                                  WITHIN_CONNECTION_1> and omitting the path
                                  inside the connection defaults to the
                                  connections root. Can be specified multiple
                                  times for multiple mappings
  --path-mappings, --path_mappings TEXT
                                  Maps path inside of containers to paths
                                  inside data-connections. Should be a comma
                                  separated list of form:
                                  <MAPPING_1>,<MAPPING_2>,... where each
                                  mapping is of the form <CONTAINER_PATH_1>:<C
                                  ONNECTION_NAME_1>:<PATH_WITHIN_CONNECTION_1>
                                  and omitting the path inside the connection
                                  defaults to the connections root. Instead of
                                  a comma-separated list, consider passing
                                  --path-mapping multiple times.
  --help                          Show this message and exit.
"""  # noqa: E501
    )


@pytest.mark.parametrize(
    ("input_mappings", "expected"),
    [
        ("", {}),
        ("container_path1:connection_1:path1", {"container_path1": "connection_1:path1"}),
        (
            "container_path1:connection_1,/container_path_2:connection-2:path2, /container-path3:connection-3",
            {
                "container_path1": "connection_1",
                "/container_path_2": "connection-2:path2",
                "/container-path3": "connection-3",
            },
        ),
    ],
)
def test_parse_run_path_mapping(input_mappings: str, expected: Dict[str, str]):
    assert _resolve_path_mapping(input_mappings) == expected
