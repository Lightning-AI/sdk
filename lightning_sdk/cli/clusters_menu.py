import sys
from typing import List

from rich.console import Console
from simple_term_menu import TerminalMenu

from lightning_sdk import Teamspace
from lightning_sdk.api.cluster_api import ClusterApi
from lightning_sdk.lightning_cloud.openapi import Externalv1Cluster, V1ProjectClusterBinding


class _ClustersMenu:
    def _get_cluster_from_interactive_menu(self, possible_clusters: List[V1ProjectClusterBinding]) -> str:
        terminal_menu = self._prepare_terminal_menu_teamspaces([cluster.cluster_id for cluster in possible_clusters])
        terminal_menu.show()

        return possible_clusters[terminal_menu.chosen_menu_index].cluster_id

    @staticmethod
    def _prepare_terminal_menu_teamspaces(cluster_ids: List[str]) -> TerminalMenu:
        title = "Please select a cluster from the following:"

        return TerminalMenu(cluster_ids, title=title, clear_menu_on_exit=True)

    def _resolve_cluster(self, teamspace: Teamspace) -> Externalv1Cluster:
        selected_cluster_id = None
        console = Console()
        try:
            selected_cluster_id = self._get_cluster_from_interactive_menu(
                possible_clusters=teamspace.cloud_account_objs
            )
            cluster_api = ClusterApi()

            return cluster_api.get_cluster(
                cluster_id=selected_cluster_id, org_id=teamspace.owner.id, project_id=teamspace.id
            )
        except KeyboardInterrupt:
            console.print("Operation cancelled by user")
            sys.exit(0)

        except Exception:
            console.print(
                f"[red]Could not find the given Cluster:[/red] {selected_cluster_id}. "
                "Please contact Lightning AI directly to resolve this issue."
            )
            sys.exit(1)
