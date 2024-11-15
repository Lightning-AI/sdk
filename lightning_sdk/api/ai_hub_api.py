from typing import List, Optional

from lightning_sdk.lightning_cloud.openapi.models import (
    CreateDeploymentRequestDefinesASpecForTheJobThatAllowsForAutoscalingJobs,
    V1Deployment,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_deployment_template_gallery_response import (
    V1DeploymentTemplateGalleryResponse,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class AIHubApi:
    def __init__(self) -> None:
        self._client = LightningClient(max_tries=3)

    def list_apis(self) -> List[V1DeploymentTemplateGalleryResponse]:
        kwargs = {"show_globally_visible": True}
        return self._client.deployment_templates_service_list_published_deployment_templates(**kwargs).templates

    def deploy_api(self, template_id: str, project_id: str, cluster_id: str, name: Optional[str]) -> V1Deployment:
        template = self._client.deployment_templates_service_get_deployment_template(template_id)
        name = name or template.name
        template.spec_v2.endpoint.id = None
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
