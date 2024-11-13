from typing import List

from lightning_sdk.lightning_cloud.openapi.models.v1_deployment_template_gallery_response import (
    V1DeploymentTemplateGalleryResponse,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class AIHubApi:
    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def list_apis(self) -> List[V1DeploymentTemplateGalleryResponse]:
        kwargs = {"show_globally_visible": True}
        return self._client.deployment_templates_service_list_published_deployment_templates(**kwargs).templates
