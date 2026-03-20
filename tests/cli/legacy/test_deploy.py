import os
import subprocess
from datetime import datetime
from pathlib import Path
from unittest import mock
from unittest.mock import ANY, MagicMock, call, patch

import pytest
import rich
from lightning_utilities.core.imports import package_available

from lightning_sdk import Machine
from lightning_sdk.cli.legacy.deploy._auth import (
    _AuthLitServe,
    _AuthMode,
    _Onboarding,
    _OnboardingStatus,
    authenticate,
    poll_verified_status,
    select_teamspace,
)
from lightning_sdk.cli.legacy.deploy.devbox import _handle_devbox, _LitServeDevbox
from lightning_sdk.cli.legacy.deploy.serve import _handle_cloud, is_connected
from lightning_sdk.cli.legacy.deploy.serve import api_impl as serve_api
from lightning_sdk.lightning_cloud.openapi import V1CloudSpaceSourceType

_LLITSERVE_AVAILABLE = package_available("litserve")


def test_serve_help():
    result = subprocess.run("lightning deploy --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning deploy [OPTIONS] COMMAND [ARGS]...

  Deploy a LitServe model.

  Example:     lightning deploy server.py --cloud # deploy to the cloud

  Example:     lightning deploy server.py  # run locally

  You can deploy the API to the cloud by running `lightning deploy server.py
  --cloud`. This will build a docker container for the server.py script and
  deploy it to the Lightning AI platform.

Options:
  --help  Show this message and exit.

Commands:
  api  Deploy a LitServe model script.
"""
    )


def test_api_help():
    result = subprocess.run("lightning deploy api --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning deploy api [OPTIONS] SCRIPT_PATH

  Deploy a LitServe model script.

Options:
  --easy                          Generate a client for the model
  --cloud                         Run the model on cloud
  --name TEXT                     Name of the deployed API (e.g.,
                                  'classification-api', 'Llama-api')
  --non-interactive, --non_interactive
                                  Do not prompt for confirmation
  --machine [CPU_SMALL|CPU|CPU_X_2|CPU_X_4|CPU_X_8|CPU_X_16|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4_SMALL|T4|T4_X_2|T4_X_4|T4_X_8|L4|L4_X_2|L4_X_4|L4_X_8|L40S|L40S_X_2|L40S_X_4|L40S_X_8|RTXP_6000|RTXP_6000_X_2|RTXP_6000_X_4|RTXP_6000_X_8|A100|A100_X_2|A100_X_4|A100_X_8|H100|H100_X_2|H100_X_4|H100_X_8|H200|H200_X_8|B200_X_8]
                                  Machine type to deploy the API on. Defaults
                                  to CPU.  [default: CPU]
  --devbox [CPU_SMALL|CPU|CPU_X_2|CPU_X_4|CPU_X_8|CPU_X_16|DATA_PREP|DATA_PREP_MAX|DATA_PREP_ULTRA|T4_SMALL|T4|T4_X_2|T4_X_4|T4_X_8|L4|L4_X_2|L4_X_4|L4_X_8|L40S|L40S_X_2|L40S_X_4|L40S_X_8|RTXP_6000|RTXP_6000_X_2|RTXP_6000_X_4|RTXP_6000_X_8|A100|A100_X_2|A100_X_4|A100_X_8|H100|H100_X_2|H100_X_4|H100_X_8|H200|H200_X_8|B200_X_8]
                                  Machine type to build the API on. Setting
                                  this argument will open the server in a
                                  Studio.
  --interruptible                 Whether the machine should be interruptible
                                  (spot) or not.
  --teamspace TEXT                The teamspace the deployment should be
                                  associated with. Defaults to the current
                                  teamspace.
  --org TEXT                      The organization owning the teamspace (if
                                  any). Defaults to the current organization.
  --user TEXT                     The user owning the teamspace (if any).
                                  Defaults to the current user.
  --cloud-account, --cloud_account TEXT
                                  The cloud account to run the deployment on.
                                  Defaults to the studio cloud account if
                                  running with studio compute env. If not
                                  provided will fall back to the teamspaces
                                  default cloud account.
  --cloud-provider, --cloud_provider TEXT
                                  The provider to create the studio on. If
                                  --cloud-account is specified, this option is
                                  prioritized.
  --port INTEGER                  The port to expose the API on.
  --min_replica, --min-replica INTEGER
                                  Number of replicas to start with.
  --max_replica, --max-replica INTEGER
                                  Number of replicas to scale up to.
  --replicas INTEGER              Deployment will start with this many
                                  replicas.
  --no_credentials, --no-credentials
                                  Whether to include credentials in the
                                  deployment.
  --help                          Show this message and exit.
"""  # noqa: E501
    )


@pytest.fixture()
def mock_cwd(tmp_path):
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_cwd)


@pytest.fixture()
def temp_script(mock_cwd):
    script_path = Path(mock_cwd) / "server.py"
    script_path.write_text(
        """import litserve as ls
if __name__ == "__main__":
    server = ls.LitServer(ls.test_examples.SimpleLitAPI())
    server.run(port=8000)"""
    )
    return script_path


@pytest.mark.skipif(not _LLITSERVE_AVAILABLE, reason="this test requires optional LitServe dependency")
@patch("subprocess.run")
def test_api_with_easy_mode(mock_subprocess, mock_cwd, temp_script):
    serve_api(temp_script, True, cloud=False)

    assert (mock_cwd / "client.py").exists(), "Client file not generated"
    mock_subprocess.assert_called_once_with(
        ["python", str(temp_script)],
        check=True,
        text=True,
    )


@pytest.mark.skipif(not _LLITSERVE_AVAILABLE, reason="this test requires optional LitServe dependency")
@patch("docker.from_env")
@patch("rich.prompt.Confirm.ask")
@patch("lightning_sdk.cli.legacy.deploy.serve.select_teamspace")
@patch("lightning_sdk.cli.legacy.deploy.serve.LitContainerApi")
@patch("lightning_sdk.serve._LitServeDeployer.run_on_cloud")
@patch("lightning_sdk.serve._LitServeDeployer._docker_build_with_logs")
@patch("lightning_sdk.cli.legacy.clusters_menu._ClustersMenu._resolve_cluster")
@patch("lightning_sdk.cli.legacy.deploy.serve.authenticate")
@patch("lightning_sdk.cli.legacy.deploy.serve.poll_verified_status")
def test_cloud_deployment(
    mock_poll_verified_status,
    mock_authenticate,
    mock_cluster_resolver,
    mock_docker_build,
    _,
    mock_litcr,
    mock_select_teamspace,
    mock_confirm,
    mock_docker,
    mock_cwd,
    temp_script,
    capsys,
):
    mock_client = mock_docker.return_value
    mock_poll_verified_status.return_value = {"onboarded": True, "verified": True}
    # Mock Docker client responses
    mock_client.ping.return_value = True
    mock_client.api.build.return_value = [{"stream": "Step 1/10"}]
    mock_client.api.push.return_value = [{"status": "Pushing"}]
    mock_cluster_resolver.return_value = None

    # Mock user confirmations
    mock_confirm.side_effect = [
        True,  # "Would you like to deploy this model to the cloud?"
        True,  # "Is the Dockerfile correct?"
    ]

    # Test with specific repository tag
    repo = "test-repo/model"
    tag = "latest"
    serve_api(temp_script, cloud=True, name=repo, tag=tag)

    mock_select_teamspace.assert_called_once()
    mock_authenticate.assert_called_once()

    # Verify Docker operations
    mock_docker_build.assert_called_once()
    mock_litcr.return_value.upload_container.assert_called_once()

    # Verify user was prompted twice
    assert mock_confirm.call_count == 1
    mock_confirm.assert_has_calls([call("Have you reviewed the Dockerfile and confirmed it's correct?", default=True)])

    # Capture and verify the output
    captured = capsys.readouterr()
    assert f"✅ Image pushed to {repo}" in captured.out


@pytest.mark.skipif(not _LLITSERVE_AVAILABLE, reason="this test requires optional LitServe dependency")
@patch("docker.from_env")
@patch("rich.prompt.Confirm.ask")
@patch("lightning_sdk.cli.legacy.deploy.serve.select_teamspace")
@patch("lightning_sdk.cli.legacy.deploy.serve.LitContainerApi")
@patch("lightning_sdk.serve._LitServeDeployer.run_on_cloud")
@patch("lightning_sdk.serve._LitServeDeployer._docker_build_with_logs")
@patch("lightning_sdk.cli.legacy.clusters_menu._ClustersMenu._resolve_cluster")
@patch("lightning_sdk.cli.legacy.deploy.serve.authenticate")
@patch("lightning_sdk.cli.legacy.deploy.serve.poll_verified_status")
def test_cloud_deployment_non_interactive(
    mock_poll_verified_status,
    mock_authenticate,
    mock_cluster_resolver,
    mock_docker_build,
    _,
    mock_litcr,
    mock_select_teamspace,
    mock_confirm,
    mock_docker,
    mock_cwd,
    temp_script,
    capsys,
):
    mock_client = mock_docker.return_value

    # Mock Docker client responses
    mock_client.ping.return_value = True
    mock_client.api.build.return_value = [{"stream": "Step 1/10"}]
    mock_client.api.push.return_value = [{"status": "Pushing"}]
    mock_cluster_resolver.return_value = None

    repo = "test-repo/model"
    tag = "latest"
    serve_api(temp_script, cloud=True, name=repo, tag=tag, non_interactive=True)

    mock_authenticate.assert_called_once_with(_AuthMode.DEPLOY, shall_confirm=False)
    mock_poll_verified_status.asssert_called_once()
    mock_select_teamspace.assert_called_once()
    mock_docker_build.assert_called_once()
    mock_litcr.return_value.upload_container.assert_called_once()

    assert mock_confirm.call_count == 0
    captured = capsys.readouterr()
    assert f"✅ Image pushed to {repo}:{tag}" in captured.out


@patch("lightning_sdk.cli.legacy.deploy.serve.datetime")
@patch("lightning_sdk.cli.legacy.deploy.serve.subprocess.run")
def test_args_with_repository(mock_subprocess, mock_dt, temp_script):
    serve_api(temp_script, name="test", cloud=False)
    mock_dt.now.assert_not_called()
    mock_subprocess.assert_called_once()


@patch("lightning_sdk.cli.legacy.deploy.serve.datetime")
@patch("lightning_sdk.cli.legacy.deploy.serve.subprocess.run")
def test_args_without_repository(mock_subprocess, mock_dt, temp_script):
    serve_api(temp_script, cloud=False)
    mock_dt.now.assert_called()
    mock_subprocess.assert_called_once()


def test_is_connected():
    assert is_connected(), "should return True when the internet is available"


@patch("lightning_sdk.cli.legacy.deploy.serve.socket.create_connection")
def test_is_connected_no_internet(mock_create_connection):
    mock_create_connection.side_effect = OSError("No internet connection")
    assert is_connected() is False, "should return True when the internet is available"


@patch("lightning_sdk.cli.legacy.deploy.serve.is_connected")
def test_handle_cloud_no_internet(mock_is_connected):
    mock_is_connected.return_value = False
    console = MagicMock()
    _handle_cloud(None, console, teamspace="test", machine=MagicMock())
    assert console.print.call_args[0][0] == "To run locally instead, use: `lightning serve [SCRIPT | server.py]`"


@patch("lightning_sdk.cli.legacy.deploy.serve.LitContainerApi")
@patch("lightning_sdk.cli.legacy.deploy._auth._resolve_teamspace")
@patch("lightning_sdk.cli.legacy.clusters_menu._ClustersMenu._resolve_cluster")
@patch("lightning_sdk.cli.legacy.deploy.serve._LitServeDeployer")
@patch("lightning_sdk.cli.legacy.deploy.serve.Confirm.ask")
@patch("lightning_sdk.cli.legacy.deploy.serve.authenticate")
@patch("lightning_sdk.cli.legacy.deploy.serve.poll_verified_status")
@patch("lightning_sdk.cli.legacy.deploy.serve._Onboarding")
@patch("lightning_sdk.cli.legacy.deploy.serve.Thread")
def test_handle_cloud_from_onboarding(
    mock_thread,
    mock_onboarding,
    mock_poll_verified_status,
    mock_authenticate,
    mock_ask,
    mock_ls_deployer,
    mock_cluster_resolver,
    _,
    mock_litcr,
    temp_script,
):
    mock_ask.return_value = True
    mock_ls_deployer.return_value.run_on_cloud.return_value = {"url": "test-url"}
    mock_poll_verified_status.return_value = {"onboarded": False, "verified": True}
    mock_cluster_resolver.return_value = None

    console = rich.console.Console()
    _handle_cloud(
        temp_script,
        console,
        teamspace="test",
        machine=MagicMock(),
    )
    mock_litcr.assert_called_once()
    mock_poll_verified_status.asssert_called_once()
    mock_authenticate.assert_called_once()
    mock_litcr.return_value.list_containers.assert_called_once_with(ANY, cloud_account=None)
    mock_ls_deployer.return_value.push_container.assert_called_once()
    mock_ls_deployer.assert_called_once()
    mock_thread.assert_called_once()
    mock_thread.return_value.start.assert_called_once()
    mock_thread.return_value.join.assert_called_once()


@patch("lightning_sdk.cli.legacy.deploy.serve.LitContainerApi")
@patch("lightning_sdk.cli.legacy.deploy._auth._resolve_teamspace")
@patch("lightning_sdk.cli.legacy.clusters_menu._ClustersMenu._resolve_cluster")
@patch("lightning_sdk.cli.legacy.deploy.serve._LitServeDeployer")
@patch("lightning_sdk.cli.legacy.deploy.serve.Confirm.ask")
@patch("lightning_sdk.cli.legacy.deploy.serve.webbrowser")
@patch("lightning_sdk.cli.legacy.deploy.serve.authenticate")
@patch("lightning_sdk.cli.legacy.deploy.serve.poll_verified_status")
def test_handle_cloud(
    mock_poll_verified_status,
    mock_authenticate,
    mock_browser,
    mock_ask,
    mock_ls_deployer,
    mock_cluster_resolver,
    _,
    mock_litcr,
    temp_script,
):
    mock_ask.return_value = True
    mock_ls_deployer.return_value.run_on_cloud.return_value = {"url": "test-url"}
    mock_cluster_resolver.return_value = None

    console = rich.console.Console()
    _handle_cloud(
        temp_script,
        console,
        teamspace="test",
        machine=MagicMock(),
    )
    mock_litcr.assert_called_once()
    mock_poll_verified_status.asssert_called_once()
    mock_authenticate.assert_called_once()
    mock_litcr.return_value.list_containers.assert_called_once_with(ANY, cloud_account=None)
    mock_ls_deployer.return_value.push_container.assert_called_once()
    mock_ls_deployer.assert_called_once()
    mock_browser.open.assert_called_once_with("test-url")


@patch("lightning_sdk.cli.legacy.deploy.serve.LitContainerApi")
@patch("lightning_sdk.cli.legacy.deploy.serve.select_teamspace")
@patch("lightning_sdk.cli.legacy.deploy.serve._LitServeDeployer")
@patch("lightning_sdk.cli.legacy.deploy.serve.Confirm.ask")
@patch("lightning_sdk.serve.DeploymentApi")
@patch("lightning_sdk.cli.legacy.deploy.serve.authenticate")
@patch("lightning_sdk.cli.legacy.deploy.serve.poll_verified_status")
def test_handle_byoc_cloud(
    mock_poll_verified_status,
    mock_authenticate,
    mock_deployment_api,
    mock_ask,
    mock_ls_deployer,
    _,
    mock_litcr,
    temp_script,
):
    mock_ask.return_value = True
    mock_deployment_api.return_value.get_deployment_by_name.return_value = None
    console = rich.console.Console()
    _handle_cloud(temp_script, console, teamspace="test", machine=MagicMock(), cloud_account="byoc-123")
    mock_litcr.assert_called_once()
    mock_poll_verified_status.asssert_called_once()
    mock_authenticate.assert_called_once()
    mock_litcr.return_value.list_containers.assert_called_once_with(ANY, cloud_account="byoc-123")
    mock_ls_deployer.return_value.push_container.assert_called_once()
    mock_ls_deployer.assert_called_once()


@patch("lightning_sdk.cli.legacy.deploy.serve.LitContainerApi")
@patch("lightning_sdk.cli.legacy.deploy.serve.select_teamspace")
@patch("lightning_sdk.cli.legacy.clusters_menu._ClustersMenu._resolve_cluster")
@patch("lightning_sdk.cli.legacy.deploy.serve._LitServeDeployer")
@patch("lightning_sdk.cli.legacy.deploy.serve.Confirm.ask")
@patch("lightning_sdk.cli.legacy.deploy.serve.authenticate")
@patch("lightning_sdk.cli.legacy.deploy.serve.poll_verified_status")
def test_handle_cloud_deployment_api(
    mock_poll_verified_status, mock_authenticate, mock_ask, mock_deployer, mock_cluster_resolver, __, ___, temp_script
):
    mock_ask.return_value = True
    mock_deployer.created = True
    mock_cluster_resolver.return_value = None
    mock_console = MagicMock()

    _handle_cloud(
        temp_script,
        mock_console,
        teamspace="test",
        machine=MagicMock(),
    )

    mock_poll_verified_status.asssert_called_once()
    mock_deployer.return_value.dockerize_api.assert_called_once()
    mock_authenticate.assert_called_once()
    mock_console.print.assert_called()
    assert "Deployment started, access at" in mock_console.print.call_args[0][0]


@patch("lightning_sdk.cli.legacy.deploy.serve.LitContainerApi")
@patch("lightning_sdk.cli.legacy.deploy.serve.select_teamspace")
@patch("lightning_sdk.cli.legacy.clusters_menu._ClustersMenu._resolve_cluster")
@patch("lightning_sdk.cli.legacy.deploy.serve._LitServeDeployer")
@patch("lightning_sdk.cli.legacy.deploy.serve.Confirm.ask")
@patch("lightning_sdk.cli.legacy.deploy.serve.authenticate")
@patch("lightning_sdk.cli.legacy.deploy.serve.poll_verified_status")
@patch("lightning_sdk.cli.legacy.deploy.serve._get_registry_url")
@pytest.mark.parametrize("cloud_account", ["byoc-123", None])
def test_handle_cloud_with_cloud_account(
    mock_registry_url,
    mock_poll_verified_status,
    mock_authenticate,
    mock_ask,
    mock_deployer,
    mock_cluster_resolver,
    mock_teamspace,
    ___,
    temp_script,
    cloud_account,
):
    mock_ask.return_value = True
    mock_deployer.created = True
    mock_console = MagicMock()
    machine = Machine.from_str("CPU")
    repository = "litserve-model"
    resolved_teamspace = MagicMock(default_cloud_account="gcp-123")

    if cloud_account is None:
        mock_cluster_resolver.return_value = "gcp-123"

    mock_teamspace.return_value = resolved_teamspace  # Mock select_teamspace to return our teamspace
    _handle_cloud(
        temp_script,
        mock_console,
        teamspace="test-teamspace",  # Pass string, not Teamspace object
        machine=machine,
        cloud_account=cloud_account,
        non_interactive=True,
        interruptible=True,
        repository=repository,
    )
    container_basename = repository.split("/")[-1]
    registry_url = mock_registry_url.return_value
    suffix = cloud_account if cloud_account is not None else "gcp-123"
    image = (
        f"{registry_url}/lit-container-{suffix}/"
        f"{resolved_teamspace.owner.name}/{resolved_teamspace.name}/{container_basename}"
    )

    mock_poll_verified_status.asssert_called_once()
    mock_deployer.return_value.dockerize_api.assert_called_once()
    mock_authenticate.assert_called_once()
    mock_console.print.assert_called()
    selected_cloud_account = cloud_account or "gcp-123"
    mock_deployer.return_value.run_on_cloud.assert_called_once_with(
        deployment_name="litserve-model",
        teamspace=resolved_teamspace,
        machine=machine,
        cloud_account=selected_cloud_account,
        port=8000,
        min_replica=0,
        max_replica=1,
        replicas=1,
        include_credentials=True,
        spot=True,
        cloudspace_id=None,
        from_onboarding=False,
        image=image,
        metric=None,
        cloud_provider=None,
    )
    assert "Deployment started, access at" in mock_console.print.call_args[0][0]


@patch("lightning_sdk.cli.legacy.deploy._auth._AuthLitServe")
def test_authenticate(mock_auth_class):
    authenticate(_AuthMode.DEPLOY)
    mock_auth_class.return_value.authenticate.assert_called_once()


@patch("lightning_sdk.cli.legacy.deploy._auth._AuthServer")
@patch("lightning_sdk.lightning_cloud.login.Auth.auth_header")
def test_auth_run_server(_, mock_authserver):
    mock_authserver.return_value.login_with_browser = MagicMock()

    auth = _AuthLitServe(_AuthMode.DEPLOY)
    auth.load = MagicMock(return_value=False)
    auth._with_env_var = False
    auth.authenticate()

    auth.load.assert_called_once()
    mock_authserver.return_value.login_with_browser.assert_called_once()


@patch("lightning_sdk.cli.legacy.deploy._auth._AuthServer")
@patch("lightning_sdk.lightning_cloud.login.Auth.auth_header")
@patch("lightning_sdk.cli.legacy.deploy._auth.Confirm")
def test_auth_run_server_confirm_browser_open(mock_auth_confirm, _, mock_authserver):
    mock_authserver.return_value.login_with_browser = MagicMock()

    auth = _AuthLitServe(_AuthMode.DEPLOY, shall_confirm=True)
    auth.load = MagicMock(return_value=False)
    auth._with_env_var = False
    auth.authenticate()

    auth.load.assert_called_once()
    mock_authserver.return_value.login_with_browser.assert_called_once()
    mock_auth_confirm.ask.assert_called_once_with(
        "[bold yellow]LitServe needs to authenticate with Lightning AI to deploy your server.[/bold yellow]\n"
        "This will open a browser window for login.\n"
        "Do you want to continue?",
        default=True,
    )


@patch("lightning_sdk.cli.legacy.deploy._auth.Teamspace")
@patch("lightning_sdk.cli.legacy.deploy._auth._get_authed_user")
@patch("lightning_sdk.cli.legacy.deploy._auth.TeamspacesMenu")
def test_select_teamspace_when_only_one_available(mock_ts_menu, mock_get_authed_user, mock_teamspace_cls):
    from lightning_sdk.user import User

    mock_menu_instance = MagicMock()
    mock_ts_menu.return_value = mock_menu_instance
    mock_menu_instance._get_possible_teamspaces.return_value = {"id": "test-teamspace"}

    mock_user_owner = MagicMock(spec=User)
    mock_menu_instance._owner = mock_user_owner

    select_teamspace(teamspace=None, org="org", user="user")
    mock_ts_menu.return_value._get_possible_teamspaces.assert_called_once()
    mock_teamspace_cls.assert_called_once_with(name="test-teamspace", org=None, user=mock_user_owner)


@patch("lightning_sdk.cli.legacy.deploy._auth._resolve_teamspace")
def test_select_teamspace(mock_resolve_teamspace):
    select_teamspace(teamspace="test-teamspace", org="org", user="user")
    mock_resolve_teamspace.assert_called_once_with(teamspace="test-teamspace", org="org", user="user")


@patch("lightning_sdk.cli.legacy.deploy._auth._get_authed_user")
@patch("lightning_sdk.cli.legacy.deploy._auth.UserApi")
def test_poll_verified_status(mock_user_api_cls, mock_get_authed_user):
    # test poll_verified_status
    mock_get_user = mock_user_api_cls.return_value.get_user = MagicMock(return_value=MagicMock(verified=False))
    assert poll_verified_status()
    mock_get_authed_user.assert_called_once()
    mock_get_user.assert_called_once()


@pytest.fixture()
def mock_onboarding():
    with patch("lightning_sdk.cli.legacy.deploy._auth.UserApi") as mock_user_api_cls:  # noqa: SIM117
        with patch("lightning_sdk.cli.legacy.deploy._auth._get_authed_user") as mock_get_authed_user:
            with patch("lightning_sdk.cli.legacy.deploy._auth.LightningClient") as mock_lightning_client:
                with patch("lightning_sdk.cli.legacy.deploy._auth.select_teamspace") as mock_select_teamspace:
                    onboarding = _Onboarding(MagicMock())
                    yield (
                        onboarding,
                        mock_user_api_cls,
                        mock_get_authed_user,
                        mock_lightning_client,
                        mock_select_teamspace,
                    )


@patch("lightning_sdk.cli.legacy.deploy._auth.Teamspace")
@patch("lightning_sdk.cli.legacy.deploy._auth.TeamspacesMenu")
def test_onboarding_select_teamspace_without_org(mock_ts_menu, mock_ts, mock_onboarding):
    (
        onboarding,
        mock_user_api_cls,
        mock_get_authed_user,
        mock_lightning_client,
        mock_select_teamspace,
    ) = mock_onboarding
    mock_ts_menu.return_value._get_possible_teamspaces.return_value = {
        "id1": {"name": "personal-teamspace", "org": None, "user": "test-user"},
    }
    mock_user_api_cls.return_value.get_user.return_value.status.verified = True
    mock_user_api_cls.return_value.get_user.return_value.status.completed_project_onboarding = False
    (
        mock_lightning_client.return_value.organizations_service_list_joinable_organizations.return_value
    ).joinable_organizations = ("org1",)
    onboarding._wait_user_onboarding = MagicMock()
    assert onboarding.verified, "User is verified"
    assert not onboarding.is_onboarded, "User is still being onboarded"
    assert onboarding.status == _OnboardingStatus.ONBOARDING, "User is still being onboarded"
    assert onboarding.can_join_org, "User can join organization"
    mock_select_teamspace.assert_not_called(), "select_teamspace shouldn't called when user is onboarding"
    onboarding.select_teamspace(None, org=None, user=None)
    onboarding._wait_user_onboarding.assert_called_once()
    mock_ts.assert_called_once_with(name="personal-teamspace", org=None, user="test-user")

    mock_ts_menu.return_value._get_possible_teamspaces.return_value = {
        "id1": {"name": "personal-teamspace", "org": None, "user": "test-user"},
        "id2": {"name": "org-teamspace", "org": "test-org", "user": "test-user"},
    }


@patch("lightning_sdk.cli.legacy.deploy._auth.Teamspace")
@patch("lightning_sdk.cli.legacy.deploy._auth.TeamspacesMenu")
def test_onboarding_select_teamspace_with_org(mock_ts_menu, mock_ts, mock_onboarding):
    (
        onboarding,
        mock_user_api_cls,
        mock_get_authed_user,
        mock_lightning_client,
        mock_select_teamspace,
    ) = mock_onboarding

    possible_teamspaces = {
        "id1": {"name": "personal-teamspace", "org": None, "user": "test-user"},
        "id2": {"name": "org-teamspace", "org": "test-org", "user": "test-user"},
    }
    mock_ts_menu.return_value._get_possible_teamspaces.return_value = possible_teamspaces
    mock_user_api_cls.return_value.get_user.return_value.status.verified = True
    mock_user_api_cls.return_value.get_user.return_value.status.completed_project_onboarding = False
    (
        mock_lightning_client.return_value.organizations_service_list_joinable_organizations.return_value
    ).joinable_organizations = ("org1",)
    onboarding._wait_user_onboarding = MagicMock()
    assert onboarding.verified, "User is verified"
    assert not onboarding.is_onboarded, "User is still being onboarded"
    assert onboarding.status == _OnboardingStatus.ONBOARDING, "User is still being onboarded"
    assert onboarding.can_join_org, "User can join organization"
    mock_select_teamspace.assert_not_called(), "select_teamspace shouldn't called when user is onboarding"
    onboarding.select_teamspace(None, org=None, user=None)
    onboarding._wait_user_onboarding.assert_called_once()
    mock_ts.assert_called_once_with(name="org-teamspace", org="test-org", user="test-user")


def test_onboarding_get_cloudspace_id(mock_onboarding):
    (
        onboarding,
        mock_user_api_cls,
        mock_get_authed_user,
        mock_lightning_client,
        mock_select_teamspace,
    ) = mock_onboarding
    cloudspaces = [
        MagicMock(display_name="scratch-studio", created_at=datetime.now(), id=1),
        MagicMock(display_name="scratch-studio-1", created_at=datetime.now(), id=2),
        MagicMock(display_name="scratch-studio-latest", created_at=datetime.now(), id=3),
    ]
    mock_lightning_client.return_value.cloud_space_service_list_cloud_spaces.return_value.cloudspaces = cloudspaces
    resp = onboarding.get_cloudspace_id(MagicMock())
    assert resp == cloudspaces[-1].id, "Should return the latest scratch cloudspace id"
    mock_lightning_client.return_value.cloud_space_service_list_cloud_spaces.assert_called_once()


def test_handle_devbox_non_python_file():
    console = MagicMock()
    _handle_devbox(
        "test",
        Path("test.cpp"),
        console,
        False,
        "CPU",
    )
    console.print.assert_called_once_with(
        "❌ Error: Only Python files (.py) are supported for development servers", style="red"
    )


def test_detect_port(tmpdir):
    test_file1 = tmpdir.join("test.py")
    test_file1.write("s.run(port=8001)")
    test_file2 = tmpdir.join("test2.py")
    test_file2.write("server.run(port=8002)")
    test_file3 = tmpdir.join("test3.py")
    test_file3.write("server.run()")
    lit_devbox = _LitServeDevbox()
    assert lit_devbox._detect_port(Path(test_file1)) == 8001
    assert lit_devbox._detect_port(Path(test_file2)) == 8002
    assert lit_devbox._detect_port(Path(test_file3)) == 8000


@patch("lightning_sdk.cli.legacy.deploy.devbox.select_teamspace")
@patch("lightning_sdk.cli.legacy.deploy.devbox.Studio")
@patch("lightning_sdk.cli.legacy.deploy.devbox._get_studio_url")
@patch("lightning_sdk.cli.legacy.deploy.devbox.webbrowser")
@patch("lightning_sdk.cli.legacy.deploy.devbox._LitServeDevbox")
@patch("lightning_sdk.cli.legacy.deploy.devbox.Confirm.ask")
@patch("lightning_sdk.cli.legacy.deploy.devbox.Thread")
@patch("lightning_sdk.cli.legacy.deploy.devbox.authenticate")
@patch("lightning_sdk.cli.legacy.deploy.devbox.poll_verified_status")
def test_handle_devbox(
    mock_poll_verified_status,
    mock_authenticate,
    mock_thread,
    mock_ask,
    mock_lit_serve_devbox,
    mock_webbrowser,
    mock_get_studio_url,
    mock_studio,
    mock_select_teamspace,
):
    mock_ask.return_value = True
    mock_lit_serve_devbox.return_value._detect_port.return_value = 8000
    mock_lit_serve_devbox.return_value.upload_folder = MagicMock()
    mock_get_studio_url.return_value = "https://lightning.ai"
    mock_console = MagicMock()
    mock_studio.return_value.run_plugin.return_value = "https://lightning.ai"
    mock_poll_verified_status.return_value = {"onboarded": True, "verified": True}
    _handle_devbox(
        "test",
        Path("test.py"),
        mock_console,
        teamspace="test-teamspace",
        org="test-org",
        user="test-user",
    )
    mock_select_teamspace.assert_called_once_with("test-teamspace", "test-org", "test-user")
    mock_authenticate.assert_called_once_with(_AuthMode.DEVBOX, shall_confirm=True)
    mock_studio.assert_called_with(
        name="test", teamspace=mock_select_teamspace.return_value, source=V1CloudSpaceSourceType.LITSERVE
    )
    mock_thread.assert_called_once_with(target=mock_studio.return_value.start, args=(Machine.CPU, False))
    mock_thread.return_value.start.assert_called()
    mock_webbrowser.open.assert_called_once_with(mock_get_studio_url.return_value)
    mock_ask.assert_called_once_with("Would you like to open your Studio in the browser?", default=True)
    mock_studio.return_value.run_plugin.assert_called_once_with("custom-port", port=8000)
    mock_studio.return_value.run_and_detach.assert_called_once_with("python test.py", timeout=10)
    mock_console.print.assert_called_with(
        "  [bold]4.[/bold] Your server will be accessible on [link=https://lightning.ai]https://lightning.ai[/link]"
    )


@patch("lightning_sdk.cli.legacy.deploy.serve._handle_devbox")
@pytest.mark.parametrize("machine", ["CPU", "T4", "A10G_X_4"])
@pytest.mark.parametrize("interruptible", [True, False])
@pytest.mark.parametrize("non_interactive", [True, False])
def test_devbox_with_machine(mock_handle_devbox, temp_script, machine, interruptible, non_interactive):
    serve_api(
        temp_script,
        devbox=machine,
        name="test-devbox",
        interruptible=interruptible,
        non_interactive=non_interactive,
        teamspace="test-teamspace",
        org="test-org",
        user="test-user",
    )
    machine = Machine.from_str(machine)
    mock_handle_devbox.assert_called_once_with(
        "test-devbox",
        temp_script,
        mock.ANY,
        non_interactive,
        machine,
        interruptible,
        "test-teamspace",
        "test-org",
        "test-user",
    )
