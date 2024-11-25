import pytest
from unittest.mock import MagicMock
from lightning_sdk import AIHub
from lightning_sdk.lightning_cloud.openapi.models.v1_env_var import V1EnvVar
from lightning_sdk.lightning_cloud.openapi.models import V1DeploymentTemplateParameterType
from lightning_sdk.lightning_cloud.openapi.models import V1EnvVar
from lightning_sdk.api.ai_hub_api import AIHubApi

class FakeV1DeploymentTemplateParameter:
    name = "Model"
    input = MagicMock(default_value="lit/test-model")
    placements = ["DEPLOYMENT_TEMPLATE_COMMAND"]
    required=True
    type = V1DeploymentTemplateParameterType.INPUT

class FakeDeploymentTemplate:
    class Job:
        command = "--model ${Model}"
        env = [V1EnvVar(name="HF_TOKEN", value="${token}")]

    class ParameterSpec:
        command = "--model ${Model}"
        parameters = [FakeV1DeploymentTemplateParameter()]
    name = "My API"
    spec_v2 = MagicMock(job=Job())
    parameter_spec = ParameterSpec()

def test_set_parameters():
    template = FakeDeploymentTemplate()
    api_arguments = {"Model": "Llama"}
    job1 = AIHubApi._set_parameters(template.spec_v2.job, template.parameter_spec.parameters, api_arguments)
    assert job1.command == "--model Llama", "User provided {model: Llama}"

    # Use default value
    template = FakeDeploymentTemplate()
    api_arguments = {}
    template.spec_v2.job = FakeDeploymentTemplate.Job()
    job2 = AIHubApi._set_parameters(template.spec_v2.job, template.parameter_spec.parameters, api_arguments)
    assert "lit/test-model" in job2.command, f"Parameter should use the default value 'lit/test-model' but is '{job2.command}'"

    template = FakeDeploymentTemplate()
    FakeV1DeploymentTemplateParameter.input = None
    with pytest.raises(ValueError, match="API reqires argument 'Model' but is not provided with api_arguments."):
        api_arguments = {"model": "Llama"}
        AIHubApi._set_parameters(template.spec_v2.job, template.parameter_spec.parameters, api_arguments)


def test_list_apis():
    hub = AIHub()
    hub._api._client = MagicMock()
    hub._api._client.deployment_templates_service_list_published_deployment_templates = MagicMock(
        return_value=MagicMock(templates=[
            MagicMock(id="1", name="API1", description="Description1", creator_username="user1"),
            MagicMock(id="2", name="API2", description="Description2", creator_username="user2"),
            MagicMock(id="3", name="API3", description="Description3", creator_username="user3")
        ])
    )
    templates = hub.list_apis()
    assert len(templates) == 3, "service api returns 3 API templates"
    assert isinstance(templates[0], dict), "AIHub.list_model returns a list of dict"
    assert templates[0].get("description") == "Description1", f"First item {templates[0]} should have description=Description1"




def test_list_api_search():
    hub = AIHub()
    hub._api = MagicMock()
    hub._api.list_apis = MagicMock(return_value=[
            MagicMock(id="1", name="cool-api", description="This is cool-api", creator_username="user1"),
        ])
    apis = hub.list_apis(search="cool-api")
    assert apis[0]["description"] == "This is cool-api"



def test_deploy():
    class FakeResponse:
        id = "dep_xxxxx"
        name = "New API"
        status = MagicMock(urls=["http://lightning.ai/example"])
        spec=MagicMock(spot=True)
    template_id = "temp_01jxxxxxxxxx"
    hub = AIHub()
    hub._authenticate = MagicMock(return_value=MagicMock(id=template_id))
    hub._api._client = MagicMock()
    hub._api._client.deployment_templates_service_get_deployment_template = MagicMock(return_value=FakeDeploymentTemplate)
    hub._api._client.jobs_service_create_deployment = MagicMock(
        return_value=FakeResponse()
    )
    AIHubApi._set_parameters = MagicMock()
    hub._api._parse_env_list = MagicMock()

    deployment = hub.deploy(template_id, cluster="public-prod", name="New API")
    assert deployment["name"] == "New API", "Deployment name is New API"
    assert deployment["base_url"] == "http://lightning.ai/example", f"base_url is decoded from the server response"
