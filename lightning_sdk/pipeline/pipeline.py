from typing import List, Optional, Union

from lightning_sdk.api import UserApi
from lightning_sdk.api.pipeline_api import PipelineApi
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.organization import Organization
from lightning_sdk.pipeline.types import MMT, Deployment, Job
from lightning_sdk.pipeline.utils import prepare_steps
from lightning_sdk.services.utilities import _get_cluster
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _resolve_org, _resolve_teamspace, _resolve_user


class Pipeline:
    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        cloud_account: Optional[str] = None,
        shared_filesystem: Optional[bool] = None,
    ) -> None:
        """The Lightning Pipeline can be used to create complex DAG.

        Arguments:
            name: The desired name of the pipeline.
            teamspace: The teamspace where the pipeline will be created.
            org: The organization where the pipeline will be created.
            user: The creator of the pipeline.
            cloud_account: The cloud account to use for the entire pipeline.
            shared_filesystem: Whether the pipeline should use a shared filesystem across all nodes.
                Note: This forces the pipeline steps to be in the cloud_account and same region
        """
        self._auth = Auth()
        self._user = None

        try:
            self._auth.authenticate()
            if user is None:
                self._user = User(name=UserApi()._get_user_by_id(self._auth.user_id).username)
        except ConnectionError as e:
            raise e

        self._name = name
        self._org = _resolve_org(org)
        self._user = _resolve_user(self._user or user)

        self._teamspace = _resolve_teamspace(
            teamspace=teamspace,
            org=org,
            user=user,
        )

        self._pipeline_api = PipelineApi()
        self._cloud_account = _get_cluster(
            client=self._pipeline_api._client, project_id=self._teamspace.id, cluster_id=cloud_account
        )
        self._shared_filesystem = shared_filesystem
        self._is_created = False

        pipeline = None

        if name.startswith("pip_"):
            pipeline = self._pipeline_api.get_pipeline_by_id(name, self._teamspace.id)

        if pipeline:
            self._name = pipeline.name
            self._is_created = True
            self._pipeline = pipeline

    def run(self, steps: List[Union[Job, Deployment, MMT]]) -> None:
        if len(steps) == 0:
            raise ValueError("The provided steps is empty")

        for step_idx, step in enumerate(steps):
            if step.name in [None, ""]:
                raise ValueError(f"The step {step_idx} requires a name")

        steps = [
            step.to_proto(self._teamspace, self._cloud_account.cluster_id or "", self._shared_filesystem)
            for step in steps
        ]

        self._pipeline = self._pipeline_api.create_pipeline(
            self._name,
            self._teamspace.id,
            prepare_steps(steps),
            self._shared_filesystem or False,
        )

    def stop(self) -> None:
        if self._pipeline is None:
            return

        self._pipeline_api.stop(self._pipeline)

    def delete(self) -> None:
        if self._pipeline is None:
            return

        self._pipeline_api.delete(self._teamspace.id, self._pipeline.id)

    @property
    def name(self) -> str:
        if self._pipeline:
            return self._pipeline.name
        return None
