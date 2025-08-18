import sys
from typing import List, Optional

from rich.console import Console
from simple_term_menu import TerminalMenu

from lightning_sdk import Teamspace
from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.lightning_cloud.openapi import V1ClusterType, V1ProjectClusterBinding


class _ClustersMenu:
    def _get_cluster_from_interactive_menu(self, possible_clusters: List[V1ProjectClusterBinding]) -> str:
        terminal_menu = self._prepare_terminal_menu_teamspaces([cluster.cluster_id for cluster in possible_clusters])
        terminal_menu.show()

        return possible_clusters[terminal_menu.chosen_menu_index].cluster_id

    @staticmethod
    def _prepare_terminal_menu_teamspaces(cluster_ids: List[str]) -> TerminalMenu:
        title = "Please select a cluster from the following:"

        return TerminalMenu(cluster_ids, title=title, clear_menu_on_exit=True)

    def _resolve_cluster(self, teamspace: Teamspace) -> Optional[str]:
        selected_cluster_id = None
        console = Console()
        try:
            selected_cluster_id = teamspace.default_cloud_account or self._get_cluster_from_interactive_menu(
                possible_clusters=teamspace.cloud_account_objs
            )

            cloud_account_api = CloudAccountApi()

            resolved_cluster_obj = cloud_account_api.get_cloud_account(
                cloud_account_id=selected_cluster_id, org_id=teamspace.owner.id, teamspace_id=teamspace.id
            )

            return None if resolved_cluster_obj.spec.cluster_type == V1ClusterType.GLOBAL else resolved_cluster_obj.id
        except KeyboardInterrupt:
            console.print("Operation cancelled by user")
            sys.exit(0)

        except Exception:
            console.print(
                f"[red]Could not find the given Cluster:[/red] {selected_cluster_id}. "
                "Please contact Lightning AI directly to resolve this issue."
            )
            sys.exit(1)
