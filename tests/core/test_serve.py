from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk import Machine
from lightning_sdk.serve import _Auth, _LitServeDeployer


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
    )


@patch("lightning_sdk.serve._AuthServer")
@patch("lightning_sdk.lightning_cloud.login.Auth.auth_header")
@patch("lightning_sdk.lightning_cloud.login.Auth.load")
def test_authenticate(mock_load, _, mock_authserver, deployer):
    mock_load.return_value = False

    def fn(cls):
        cls._with_env_var = False

    with patch.object(_Auth, "__post_init__", lambda self: fn(self)):
        deployer.authenticate()
        mock_authserver.return_value.login_with_browser.assert_called_once()


def test_push_container(deployer):
    teamspace = MagicMock()
    lit_cr = MagicMock()
    lit_cr.upload_container.return_value = []
    progress = MagicMock()
    deployer.push_container("repository", "tag", teamspace, lit_cr, progress, "cloud_account")
    lit_cr.authenticate.assert_called_once()
    lit_cr.upload_container.assert_called_once_with("repository", teamspace, tag="tag", cloud_account="cloud_account")
