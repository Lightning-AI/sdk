from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk import AIHub
from lightning_sdk.api.ai_hub_api import AIHubApi
from lightning_sdk.lightning_cloud.openapi.models import V1DeploymentTemplateParameterType
from lightning_sdk.lightning_cloud.openapi.models.v1_env_var import V1EnvVar


class FakeV1DeploymentTemplateParameter:
    name = "Model"
    input = MagicMock(default_value="lit/test-model")
    placements = ["DEPLOYMENT_TEMPLATE_COMMAND"]  # noqa: RUF012
    required = True
    type = V1DeploymentTemplateParameterType.INPUT


class FakeV1DeploymentTemplateParameterCheckbox:
    name = "ENABLE"
    checkbox = MagicMock(true_value="--enable", is_checked=False, false_value="", value="")
    placements = ["DEPLOYMENT_TEMPLATE_COMMAND"]  # noqa: RUF012
    type = V1DeploymentTemplateParameterType.CHECKBOX


class FakeDeploymentTemplate:
    class Job:
        command = "--model ${Model} ${ENABLE}"
        env = [V1EnvVar(name="HF_TOKEN", value="${token}")]  # noqa: RUF012

    class ParameterSpec:
        command = "--model ${Model}"
        parameters = [FakeV1DeploymentTemplateParameter(), FakeV1DeploymentTemplateParameterCheckbox()]  # noqa: RUF012

    name = "My API"
    spec_v2 = MagicMock(job=Job())
    parameter_spec = ParameterSpec()


def test_set_parameters():
    template = FakeDeploymentTemplate()
    api_arguments = {"Model": "Llama", "ENABLE": False}
    job1 = AIHubApi._set_parameters(template.spec_v2.job, template.parameter_spec.parameters, api_arguments)
    assert job1.command == "--model Llama ", "User provided {model: Llama, ENABLE: False}"

    template = FakeDeploymentTemplate()
    template.spec_v2.job = FakeDeploymentTemplate.Job()
    api_arguments = {"Model": "Llama", "ENABLE": True}
    job2 = AIHubApi._set_parameters(template.spec_v2.job, template.parameter_spec.parameters, api_arguments)
    assert job2.command == "--model Llama --enable", "User provided {model: Llama, ENABLE: True}"

    # Use default value
    template = FakeDeploymentTemplate()
    api_arguments = {}
    template.spec_v2.job = FakeDeploymentTemplate.Job()
    job3 = AIHubApi._set_parameters(template.spec_v2.job, template.parameter_spec.parameters, api_arguments)
    assert (
        "lit/test-model" in job3.command
    ), f"Parameter should use the default value 'lit/test-model' but is '{job3.command}'"

    template = FakeDeploymentTemplate()
    FakeV1DeploymentTemplateParameter.input = None
    api_arguments = {"model": "Llama"}
    with pytest.raises(ValueError, match="API requires argument 'Model' but is not provided with api_arguments."):
        AIHubApi._set_parameters(template.spec_v2.job, template.parameter_spec.parameters, api_arguments)


def test_list_apis():
    hub = AIHub()
    hub._api._client = MagicMock()
    hub._api._client.deployment_templates_service_list_published_deployment_templates = MagicMock(
        return_value=MagicMock(
            templates=[
                MagicMock(id="1", name="API1", description="Description1", creator_username="user1"),
                MagicMock(id="2", name="API2", description="Description2", creator_username="user2"),
                MagicMock(id="3", name="API3", description="Description3", creator_username="user3"),
            ]
        )
    )
    templates = hub.list_apis()
    assert len(templates) == 3, "service api returns 3 API templates"
    assert isinstance(templates[0], dict), "AIHub.list_model returns a list of dict"
    assert (
        templates[0].get("description") == "Description1"
    ), f"First item {templates[0]} should have description=Description1"


def test_list_api_search():
    hub = AIHub()
    hub._api = MagicMock()
    hub._api.list_apis = MagicMock(
        return_value=[
            MagicMock(id="1", name="cool-api", description="This is cool-api", creator_username="user1"),
        ]
    )
    apis = hub.list_apis(search="cool-api")
    assert apis[0]["description"] == "This is cool-api"


@patch("lightning_sdk.ai_hub._resolve_teamspace")
def test_run(mock_resolve_teamspace):
    class FakeResponse:
        id = "dep_xxxxx"
        name = "New API"
        status = MagicMock(urls=["http://lightning.ai/example"])
        spec = MagicMock(spot=True)

    class FakeOrg:
        name = "org-name"

    class FakeTeamspace:
        id = "mock-ts-id"
        name = "mock-ts"
        owner = FakeOrg()

    template_id = "temp_01jxxxxxxxxx"
    hub = AIHub()
    hub._api._client = MagicMock()
    hub._api._client.deployment_templates_service_get_deployment_template = MagicMock(
        return_value=FakeDeploymentTemplate
    )
    hub._api._client.jobs_service_create_deployment = MagicMock(return_value=FakeResponse())
    AIHubApi._set_parameters = MagicMock()
    hub._api._parse_env_list = MagicMock()

    mock_resolve_teamspace.return_value = FakeTeamspace()

    deployment = hub.run(template_id, cloud_account="public-prod", name="New API", teamspace="mock-ts", org="mock-org")
    assert deployment.name == "New API", "Deployment name is New API"
    assert deployment.status.urls[0] == "http://lightning.ai/example", "base_url is decoded from the server response"
