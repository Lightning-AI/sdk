from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk import Machine
from lightning_sdk.cli.serve import _LitServeDeployer


@pytest.fixture()
def deployer():
    return _LitServeDeployer(None, None)


@patch("lightning_sdk.serve.Deployment")
def test_run_on_cloud_already_started(mock_deployment, deployer):
    teamspace = MagicMock()
    teamspace.owner = MagicMock()
    teamspace.owner.name = "owner"
    teamspace.name = "name"
    image = "scratch"
    mock_deployment.return_value.is_started = True
    deployer._update_deployment = MagicMock()

    deployer.run_on_cloud("example", teamspace=teamspace, image=image, port=8000)
    deployer._update_deployment.assert_called_once()


@patch("lightning_sdk.serve.AutoScaleConfig")
@patch("lightning_sdk.serve.Deployment")
def test_run_on_cloud(mock_deployment, mock_autoscale, deployer):
    teamspace = MagicMock()
    teamspace.owner = MagicMock()
    teamspace.owner.name = "owner"
    teamspace.name = "name"
    image = "scratch"
    mock_deployment.return_value.is_started = False
    deployer.run_on_cloud("example", teamspace=teamspace, image=image, port=8000)
    mock_deployment.assert_called_with("example", teamspace)
    mock_deployment.return_value.start.assert_called_with(
        machine=Machine.CPU,
        image="scratch",
        ports=[8000],
        autoscale=mock_autoscale.return_value,
        replicas=1,
        spot=None,
        cloud_account=None,
        include_credentials=True,
        cloudspace_id=None,
        from_onboarding=False,
    )


def test_push_container(deployer):
    teamspace = MagicMock()
    lit_cr = MagicMock()
    lit_cr.upload_container.return_value = []
    gen = deployer.push_container("repository", "tag", teamspace, lit_cr=lit_cr, cloud_account="cloud_account")
    last_line = None
    for line in gen:
        last_line = line
    assert isinstance(last_line, dict), "Expected a dictionary"
    assert last_line["finish"], "Last line must have finish=True"
    assert isinstance(last_line["image"], str), "Last line must contain the docker repo image"
    lit_cr.authenticate.assert_called_once()
    lit_cr.upload_container.assert_called_once_with(
        "repository", teamspace, tag="tag", cloud_account="cloud_account", platform=None
    )
