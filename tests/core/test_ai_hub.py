from unittest.mock import MagicMock
from lightning_sdk import AIHub


def test_ai_hub_list_apis():
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
