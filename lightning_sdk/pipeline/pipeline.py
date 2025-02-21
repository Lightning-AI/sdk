from typing import List, Union

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
    ) -> None:
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
            org=self._org,
            user=self._user if self._org is None else None,
        )
        if self._teamspace is None:
            raise ValueError("You need to pass a teamspace or an org for your deployment.")

        self._pipeline_api = PipelineApi()

        self._cloud_account = _get_cluster(client=self._pipeline_api._client, project_id=self._teamspace.id)
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

        steps = [step.to_proto() for step in steps]

        self._pipeline = self._pipeline_api.create_pipeline(self._name, self._teamspace, prepare_steps(steps))
