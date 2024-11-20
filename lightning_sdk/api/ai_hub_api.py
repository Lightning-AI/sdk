import re
from typing import List, Optional

import backoff

from lightning_sdk.lightning_cloud.openapi.models import (
    CreateDeploymentRequestDefinesASpecForTheJobThatAllowsForAutoscalingJobs,
    V1Deployment,
    V1ParameterizationSpec,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_deployment_template_gallery_response import (
    V1DeploymentTemplateGalleryResponse,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class AIHubApi:
    def __init__(self) -> None:
        self._client = LightningClient(max_tries=3)

    @backoff.on_predicate(backoff.expo, lambda x: not x, max_tries=5)
    def list_apis(self, search_query: str) -> List[V1DeploymentTemplateGalleryResponse]:
        kwargs = {"show_globally_visible": True}
        return self._client.deployment_templates_service_list_published_deployment_templates(
            search_query=search_query, **kwargs
        ).templates

    @staticmethod
    def _parse_and_update_args(cmd: str, **kwargs: dict) -> list:
        """Parse the command and update the arguments with the provided kwargs.

        >>> _parse_and_update_args("--arg1 1 --arg2=2", arg1=3)
        ['--arg1 3']
        """
        keys = [key.lstrip("-") for key in re.findall(r"--\w+", cmd)]
        arguments = {}
        for key in keys:
            if key in kwargs:
                arguments[key] = kwargs[key]
        return [f"--{k} {v}" for k, v in arguments.items()]

    @staticmethod
    def _resolve_api_arguments(parameter_spec: "V1ParameterizationSpec", **kwargs: dict) -> str:
        return " ".join(AIHubApi._parse_and_update_args(parameter_spec.command, **kwargs))

    def deploy_api(
        self, template_id: str, project_id: str, cluster_id: str, name: Optional[str], **kwargs: dict
    ) -> V1Deployment:
        template = self._client.deployment_templates_service_get_deployment_template(template_id)
        name = name or template.name
        template.spec_v2.endpoint.id = None
        command = self._resolve_api_arguments(template.parameter_spec, **kwargs)
        template.spec_v2.job.command = command
        return self._client.jobs_service_create_deployment(
            project_id=project_id,
            body=CreateDeploymentRequestDefinesASpecForTheJobThatAllowsForAutoscalingJobs(
                autoscaling=template.spec_v2.autoscaling,
                cluster_id=cluster_id,
                endpoint=template.spec_v2.endpoint,
                name=name,
                replicas=0,
                spec=template.spec_v2.job,
            ),
        )
