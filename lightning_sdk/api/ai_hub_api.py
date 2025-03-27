import traceback
import warnings
from typing import Dict, List, Optional, Tuple, Union

import backoff

from lightning_sdk.api.deployment_api import apply_change
from lightning_sdk.api.utils import _machine_to_compute_name
from lightning_sdk.lightning_cloud.openapi.models import (
    CreateDeploymentRequestDefinesASpecForTheJobThatAllowsForAutoscalingJobs,
    V1Deployment,
    V1DeploymentTemplate,
    V1DeploymentTemplateParameter,
    V1DeploymentTemplateParameterPlacement,
    V1DeploymentTemplateParameterType,
    V1JobSpec,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_deployment_template_gallery_response import (
    V1DeploymentTemplateGalleryResponse,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine


class AIHubApi:
    def __init__(self) -> None:
        self._client = LightningClient(max_tries=3)

    def api_info(self, api_id: str) -> Tuple[V1DeploymentTemplate, List[Dict[str, str]]]:
        try:
            template = self._client.deployment_templates_service_get_deployment_template(api_id)
        except Exception as e:
            stack_trace = traceback.format_exc()
            if "record not found" in stack_trace:
                raise ValueError(f"api_id={api_id} not found.") from None
            raise e

        api_arguments = []
        for param in template.parameter_spec.parameters:
            default = None
            if param.type == V1DeploymentTemplateParameterType.INPUT and param.input:
                default = param.input.default_value
            if param.type == V1DeploymentTemplateParameterType.SELECT and param.select:
                default = param.select.options[0]
            if param.type == V1DeploymentTemplateParameterType.CHECKBOX and param.checkbox:
                default = (
                    (param.checkbox.true_value or "True")
                    if param.checkbox.is_checked
                    else (param.checkbox.false_value or "False")
                )

            api_arguments.append(
                {
                    "name": param.name,
                    "short_description": param.short_description,
                    "required": param.required,
                    "type": param.type,
                    "default": default,
                }
            )
        return template, api_arguments

    @backoff.on_predicate(backoff.expo, lambda x: not x, max_tries=5)
    def list_apis(self, search_query: str) -> List[V1DeploymentTemplateGalleryResponse]:
        kwargs = {"show_globally_visible": True}
        return self._client.deployment_templates_service_list_published_deployment_templates(
            search_query=search_query, **kwargs
        ).templates

    @staticmethod
    def _update_parameters(
        job: V1JobSpec, placements: List[V1DeploymentTemplateParameterPlacement], pattern: str, value: str
    ) -> None:
        for placement in placements:
            if placement == V1DeploymentTemplateParameterPlacement.COMMAND:
                job.command = job.command.replace(pattern, str(value))
            if placement == V1DeploymentTemplateParameterPlacement.ENTRYPOINT:
                job.entrypoint = job.entrypoint.replace(pattern, str(value))

            if placement == V1DeploymentTemplateParameterPlacement.ENV:
                for e in job.env:
                    if e.value == pattern:
                        e.value = str(value)

    @staticmethod
    def _set_parameters(
        job: V1JobSpec, parameters: List[V1DeploymentTemplateParameter], api_arguments: Dict[str, str]
    ) -> V1JobSpec:
        for p in parameters:
            if p.name not in api_arguments:
                if p.type == V1DeploymentTemplateParameterType.INPUT and p.input and p.input.default_value:
                    api_arguments[p.name] = p.input.default_value

                if p.type == V1DeploymentTemplateParameterType.SELECT and p.select and len(p.select.options) > 0:
                    api_arguments[p.name] = p.select.options[0]

                if p.type == V1DeploymentTemplateParameterType.CHECKBOX and p.checkbox:
                    api_arguments[p.name] = (
                        (p.checkbox.true_value or "") if p.checkbox.is_checked else (p.checkbox.false_value or "")
                    )

        for p in parameters:
            name = p.name
            pattern = f"${{{name}}}"
            if name in api_arguments:
                if p.type == V1DeploymentTemplateParameterType.CHECKBOX and p.checkbox:
                    api_arguments[p.name] = (
                        (p.checkbox.true_value or "") if api_arguments[name] is True else (p.checkbox.false_value or "")
                    )
                AIHubApi._update_parameters(job, p.placements, pattern, api_arguments[name])
            elif not p.required:
                AIHubApi._update_parameters(job, p.placements, pattern, "")
            else:
                raise ValueError(f"API requires argument '{p.name}' but is not provided with api_arguments.")

        return job

    def run_api(
        self,
        template_id: str,
        project_id: str,
        cloud_account: str,
        name: Optional[str],
        api_arguments: Dict[str, str],
        machine: Optional[Union[str, Machine]],
        quantity: Optional[int],
    ) -> V1Deployment:
        template = self._client.deployment_templates_service_get_deployment_template(template_id)
        name = name or template.name
        template.spec_v2.endpoint.id = None

        # These are needed to ensure templates with a max replicas of 0 will start on creation
        if template.spec_v2.autoscaling.max_replicas == "0":
            template.spec_v2.autoscaling.max_replicas = "1"
        if not template.spec_v2.autoscaling.enabled:
            template.spec_v2.autoscaling.enabled = True

        AIHubApi._set_parameters(template.spec_v2.job, template.parameter_spec.parameters, api_arguments)
        if machine and isinstance(machine, Machine):
            apply_change(template.spec_v2.job, "instance_name", _machine_to_compute_name(machine))
            apply_change(template.spec_v2.job, "instance_type", _machine_to_compute_name(machine))
        elif machine and isinstance(machine, str):
            apply_change(template.spec_v2.job, "instance_name", machine)
            apply_change(template.spec_v2.job, "instance_type", machine)

        if quantity != template.spec_v2.job.quantity:
            # If the quantity is different from the published template quantity, override it with warnging
            warnings.warn(
                "Overriding the quantity of the template with the provided quantity. "
                "This may result in unexpected behavior. "
                f"Please verify the template (https://lightning.ai/lightning-ai/ai-hub/{template_id}) "
                "and asscoiated parameters before running."
            )
            apply_change(template.spec_v2.job, "quantity", quantity)

        # Override the cluster_id with the cloud_account if it is provided
        if len(cloud_account) > 0:
            apply_change(template.spec_v2.job, "cluster_id", cloud_account)
        return self._client.jobs_service_create_deployment(
            project_id=project_id,
            body=CreateDeploymentRequestDefinesASpecForTheJobThatAllowsForAutoscalingJobs(
                autoscaling=template.spec_v2.autoscaling,
                cluster_id=cloud_account,
                endpoint=template.spec_v2.endpoint,
                name=name,
                replicas=1,
                spec=template.spec_v2.job,
                parent_template_id=template_id,
            ),
        )

    def delete_api(self, deployment_id: str, teamspace_id: str) -> None:
        self._client.jobs_service_delete_deployment(project_id=teamspace_id, id=deployment_id)
