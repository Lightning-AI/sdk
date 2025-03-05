from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk import Machine
from lightning_sdk.serve import _LitServeDeployer


@patch("lightning_sdk.serve.Deployment")
def test_run_on_cloud_already_started(mock_deployment):
    deployer = _LitServeDeployer()
    teamspace = MagicMock()
    teamspace.owner = MagicMock()
    teamspace.owner.name = "owner"
    teamspace.name = "name"
    image = "scratch"
    ports = [8000]
    mock_deployment.return_value.is_started = True
    with pytest.raises(RuntimeError, match="Deployment with name example already running."):
        deployer._run_on_cloud("example", teamspace=teamspace, image=image, ports=ports)


@patch("lightning_sdk.serve.AutoScaleConfig")
@patch("lightning_sdk.serve.Deployment")
def test_run_on_cloud(mock_deployment, mock_autoscale):
    deployer = _LitServeDeployer()
    teamspace = MagicMock()
    teamspace.owner = MagicMock()
    teamspace.owner.name = "owner"
    teamspace.name = "name"
    image = "scratch"
    ports = [8000]
    mock_deployment.return_value.is_started = False
    deployer._run_on_cloud("example", teamspace=teamspace, image=image, ports=ports)
    mock_deployment.assert_called_with("example", teamspace)
    mock_deployment.return_value.start.assert_called_with(
        machine=Machine.CPU,
        image="scratch",
        ports=[8000],
        autoscale=mock_autoscale.return_value,
        replicas=None,
        spot=None,
        cloud_account=None,
    )
