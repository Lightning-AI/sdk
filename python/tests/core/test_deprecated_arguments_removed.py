import inspect

import click
import pytest

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.deployment import Deployment
from lightning_sdk.job import Job
from lightning_sdk.mmt import MMT
from lightning_sdk.pipeline import Pipeline
from lightning_sdk.pipeline.steps import DeploymentStep, JobStep, MMTStep
from lightning_sdk.sandbox import Sandbox
from lightning_sdk.serve import _LitServeDeployer
from lightning_sdk.studio import Studio


@pytest.mark.parametrize(
    ("callable_obj", "removed_names"),
    [
        (CloudAccountApi.resolve_cloud_account, {"cloud_account", "cloud_provider"}),
        (Deployment.start, {"cloud_account", "cloud_provider"}),
        (Deployment.update, {"cloud_account"}),
        (Job.run, {"cloud_account", "cloud_provider", "artifacts_local", "artifacts_remote"}),
        (MMT.run, {"cloud_account", "cloud_provider", "artifacts_local", "artifacts_remote"}),
        (Pipeline.__init__, {"cloud_account", "cloud_provider"}),
        (DeploymentStep.__init__, {"cloud_account", "cloud_provider"}),
        (JobStep.__init__, {"cloud_account", "cloud_provider"}),
        (MMTStep.__init__, {"cloud_account"}),
        (Sandbox.__init__, {"cloud_account", "cloud_provider"}),
        (_LitServeDeployer._update_deployment, {"cloud_account"}),
        (_LitServeDeployer.run_on_cloud, {"cloud_account", "cloud_provider"}),
        (Studio.__init__, {"cloud_account", "cloud_provider"}),
    ],
)
def test_deprecated_sdk_arguments_are_removed(callable_obj, removed_names):
    signature = inspect.signature(callable_obj)

    assert removed_names.isdisjoint(signature.parameters)


def _command_options(command: click.Command) -> set[str]:
    options: set[str] = set()
    for param in command.params:
        if isinstance(param, click.Option):
            options.update(param.opts)
            options.update(param.secondary_opts)
    return options


@pytest.mark.parametrize(
    ("command_path", "removed_options"),
    [
        (
            "lightning_sdk.cli.api.deploy:deploy_api",
            {"--cloud-account", "--cloud_account", "--cloud-provider", "--cloud_provider"},
        ),
        ("lightning_sdk.cli.deployment.create:create_deployment", {"--cloud-account", "--cloud_account"}),
        (
            "lightning_sdk.cli.deployment.update:update_deployment",
            {"--cloud-account", "--cloud_account"},
        ),
        ("lightning_sdk.cli.job.run:run_job", {"--cloud-account", "--cloud_account"}),
        (
            "lightning_sdk.cli.legacy.deploy.serve:api",
            {"--cloud-account", "--cloud_provider", "--cloud-provider"},
        ),
        (
            "lightning_sdk.cli.legacy.run:job",
            {"--cloud-account", "--cloud_account", "--cloud-provider", "--cloud_provider"},
        ),
        ("lightning_sdk.cli.legacy.run:mmt", {"--cloud-account", "--cloud_account"}),
        ("lightning_sdk.cli.mmt.run:run_mmt", {"--cloud-account", "--cloud_account"}),
        ("lightning_sdk.cli.studio.connect:connect_studio", {"--cloud-account", "--cloud-provider"}),
        ("lightning_sdk.cli.studio.create:create_studio", {"--cloud-account", "--cloud-provider"}),
        ("lightning_sdk.cli.studio.start:start_studio", {"--cloud-account", "--cloud-provider"}),
    ],
)
def test_deprecated_cli_options_are_removed(command_path, removed_options):
    module_name, command_name = command_path.split(":")
    module = __import__(module_name, fromlist=[command_name])
    command = getattr(module, command_name)

    assert removed_options.isdisjoint(_command_options(command))
