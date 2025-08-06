from unittest.mock import MagicMock, patch

from lightning_sdk.cli.clusters_menu import _ClustersMenu
from lightning_sdk.lightning_cloud.openapi import Externalv1Cluster, V1ClusterType, V1ProjectClusterBinding


class TestClustersMenu:
    def setup_method(self):
        self.clusters_menu = _ClustersMenu()

        self.mock_cluster_bindings = [
            MagicMock(spec=V1ProjectClusterBinding, cluster_id="cluster-1"),
            MagicMock(spec=V1ProjectClusterBinding, cluster_id="cluster-2"),
            MagicMock(spec=V1ProjectClusterBinding, cluster_id="cluster-3"),
        ]

        self.mock_teamspace = MagicMock()
        self.mock_teamspace.default_cloud_account = None
        self.mock_teamspace.cloud_account_objs = self.mock_cluster_bindings
        self.mock_teamspace.owner.id = "owner-id"
        self.mock_teamspace.id = "teamspace-id"

    def test_get_cluster_from_interactive_menu(self):
        mock_terminal_menu = MagicMock()
        mock_terminal_menu.chosen_menu_index = 1

        self.clusters_menu._prepare_terminal_menu_teamspaces = MagicMock(return_value=mock_terminal_menu)
        result = self.clusters_menu._get_cluster_from_interactive_menu(self.mock_cluster_bindings)

        assert result == "cluster-2"
        mock_terminal_menu.show.assert_called_once()
        self.clusters_menu._prepare_terminal_menu_teamspaces.assert_called_once_with(
            ["cluster-1", "cluster-2", "cluster-3"]
        )

    @patch("lightning_sdk.cli.clusters_menu.CloudAccountApi")
    @patch("lightning_sdk.cli.clusters_menu.Console")
    @patch("sys.exit")
    def test_resolve_cluster_from_teamspace_byoc(self, mock_exit, mock_console_class, mock_cloud_account_api_class):
        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        mock_cloud_account_api = MagicMock()
        mock_cloud_account_api_class.return_value = mock_cloud_account_api

        expected_cluster = MagicMock(spec=Externalv1Cluster)
        expected_cluster.spec.cluster_type = V1ClusterType.BYOC
        expected_cluster.id = "cluster-2"
        mock_cloud_account_api.get_cloud_account.return_value = expected_cluster

        self.mock_teamspace.default_cloud_account = "cluster-2"
        result = self.clusters_menu._resolve_cluster(self.mock_teamspace)

        assert result == "cluster-2"

        mock_cloud_account_api.get_cloud_account.assert_called_once_with(
            cloud_account_id="cluster-2", org_id=self.mock_teamspace.owner.id, teamspace_id=self.mock_teamspace.id
        )

    @patch("lightning_sdk.cli.clusters_menu.CloudAccountApi")
    @patch("lightning_sdk.cli.clusters_menu.Console")
    @patch("sys.exit")
    def test_resolve_cluster_from_teamspace_lightning_saas(
        self, mock_exit, mock_console_class, mock_cloud_account_api_class
    ):
        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        mock_cloud_account_api = MagicMock()
        mock_cloud_account_api_class.return_value = mock_cloud_account_api

        expected_cluster = MagicMock(spec=Externalv1Cluster)
        expected_cluster.spec.cluster_type = V1ClusterType.GLOBAL
        expected_cluster.id = "cluster-2"
        mock_cloud_account_api.get_cloud_account.return_value = expected_cluster

        self.mock_teamspace.default_cloud_account = "cluster-2"
        result = self.clusters_menu._resolve_cluster(self.mock_teamspace)

        # lightning saas is always None because there are multiple lightning saas global clusters but only one
        # lightning saas storage backend.
        assert result is None

        mock_cloud_account_api.get_cloud_account.assert_called_once_with(
            cloud_account_id="cluster-2", org_id=self.mock_teamspace.owner.id, teamspace_id=self.mock_teamspace.id
        )

    @patch("lightning_sdk.cli.clusters_menu.TerminalMenu")
    def test_prepare_terminal_menu_teamspaces(self, mock_terminal_menu_class):
        cluster_ids = ["cluster-a", "cluster-b", "cluster-c"]
        result = self.clusters_menu._prepare_terminal_menu_teamspaces(cluster_ids)

        mock_terminal_menu_class.assert_called_once_with(
            cluster_ids, title="Please select a cluster from the following:", clear_menu_on_exit=True
        )
        assert result == mock_terminal_menu_class.return_value

    @patch("lightning_sdk.cli.clusters_menu.CloudAccountApi")
    @patch("lightning_sdk.cli.clusters_menu.Console")
    @patch("sys.exit")
    def test_resolve_cluster_success(self, mock_exit, mock_console_class, mock_cloud_account_api_class):
        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        mock_cloud_account_api = MagicMock()
        mock_cloud_account_api_class.return_value = mock_cloud_account_api

        expected_cluster = MagicMock(spec=Externalv1Cluster)
        mock_cloud_account_api.get_cloud_account.return_value = expected_cluster

        self.clusters_menu._get_cluster_from_interactive_menu = MagicMock(return_value="cluster-2")

        self.clusters_menu._resolve_cluster(self.mock_teamspace)
        self.clusters_menu._get_cluster_from_interactive_menu.assert_called_once_with(
            possible_clusters=self.mock_teamspace.cloud_account_objs
        )
        mock_cloud_account_api.get_cloud_account.assert_called_once_with(
            cloud_account_id="cluster-2", org_id=self.mock_teamspace.owner.id, teamspace_id=self.mock_teamspace.id
        )
        mock_exit.assert_not_called()

    @patch("lightning_sdk.cli.clusters_menu.Console")
    @patch("sys.exit")
    def test_resolve_cluster_keyboard_interrupt(self, mock_exit, mock_console_class):
        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        self.clusters_menu._get_cluster_from_interactive_menu = MagicMock(side_effect=KeyboardInterrupt())

        self.clusters_menu._resolve_cluster(self.mock_teamspace)

        mock_console.print.assert_called_once_with("Operation cancelled by user")
        mock_exit.assert_called_once_with(0)

    @patch("lightning_sdk.cli.clusters_menu.Console")
    @patch("sys.exit")
    def test_resolve_cluster_exception(self, mock_exit, mock_console_class):
        mock_console = MagicMock()
        mock_console_class.return_value = mock_console

        test_error = ValueError("Test error")
        self.clusters_menu._get_cluster_from_interactive_menu = MagicMock(side_effect=test_error)

        self.clusters_menu._resolve_cluster(self.mock_teamspace)

        mock_console.print.assert_called_once()  # Check that print was called
        assert "Could not find the given Cluster" in mock_console.print.call_args[0][0]
        assert "None" in mock_console.print.call_args[0][0]
        mock_exit.assert_called_once_with(1)
