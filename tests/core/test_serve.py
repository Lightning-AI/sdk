from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk import Machine
from lightning_sdk.serve import _Auth, _LitServeDeployer


@patch("lightning_sdk.serve.Deployment")
def test_run_on_cloud_already_started(mock_deployment):
    deployer = _LitServeDeployer()
    teamspace = MagicMock()
    teamspace.owner = MagicMock()
    teamspace.owner.name = "owner"
    teamspace.name = "name"
    image = "scratch"
    mock_deployment.return_value.is_started = True
    with pytest.raises(RuntimeError, match="Deployment with name example already running."):
        deployer._run_on_cloud("example", teamspace=teamspace, image=image, port=8000)


@patch("lightning_sdk.serve.AutoScaleConfig")
@patch("lightning_sdk.serve.Deployment")
def test_run_on_cloud(mock_deployment, mock_autoscale):
    deployer = _LitServeDeployer()
    teamspace = MagicMock()
    teamspace.owner = MagicMock()
    teamspace.owner.name = "owner"
    teamspace.name = "name"
    image = "scratch"
    mock_deployment.return_value.is_started = False
    deployer._run_on_cloud("example", teamspace=teamspace, image=image, port=8000)
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
    )


@patch("lightning_sdk.serve._AuthServer")
@patch("lightning_sdk.lightning_cloud.login.Auth.auth_header")
@patch("lightning_sdk.lightning_cloud.login.Auth.load")
def test_authenticate(mock_load, mock_auth_header, mock_authserver):
    mock_load.return_value = False

    def fn(cls):
        cls._with_env_var = False

    with patch.object(_Auth, "__post_init__", lambda self: fn(self)):
        deployer = _LitServeDeployer()
        deployer.authenticate()
        mock_authserver.return_value.login_with_browser.assert_called_once()
