from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk import Machine
from lightning_sdk.serve import _Auth, _LitServeDeployer, authenticate


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


@patch("lightning_sdk.serve._Auth")
def test_authenticate(mock_auth_class):
    authenticate()
    mock_auth_class.return_value.authenticate.assert_called_once()


@patch("lightning_sdk.serve._AuthServer")
@patch("lightning_sdk.lightning_cloud.login.Auth.auth_header")
def test_auth_run_server(_, mock_authserver):
    mock_authserver.return_value.login_with_browser = MagicMock()

    auth = _Auth()
    auth.load = MagicMock(return_value=False)
    auth._with_env_var = False
    auth.authenticate()

    auth.load.assert_called_once()
    mock_authserver.return_value.login_with_browser.assert_called_once()


@patch("lightning_sdk.serve._AuthServer")
@patch("lightning_sdk.lightning_cloud.login.Auth.auth_header")
@patch("lightning_sdk.serve.Confirm")
def test_auth_run_server_confirm_browser_open(mock_confirm, _, mock_authserver):
    mock_authserver.return_value.login_with_browser = MagicMock()

    auth = _Auth(shall_confirm=True)
    auth.load = MagicMock(return_value=False)
    auth._with_env_var = False
    auth.authenticate()

    auth.load.assert_called_once()
    mock_authserver.return_value.login_with_browser.assert_called_once()
    mock_confirm.ask.assert_called_once_with(
        "Authenticating with Lightning AI. This will open a browser window. Continue?", default=True
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
