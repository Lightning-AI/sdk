from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.api.api_key_api import ApiKeyApi


def _member_role() -> SimpleNamespace:
    # MagicMock(name=...) sets the mock's repr name, not role.name — use SimpleNamespace.
    return SimpleNamespace(id="role-member", name="Organization Member")


@pytest.fixture()
def mock_client() -> MagicMock:
    with patch("lightning_sdk.api.api_key_api.LightningClient") as client_cls:
        client = MagicMock()
        client_cls.return_value = client
        yield client


def test_get_or_create_default_returns_existing_org_key(mock_client: MagicMock) -> None:
    org = MagicMock()
    org.id = "org-1"

    mock_client.auth_service_get_user.return_value = MagicMock(id="user-1")
    mock_client.projects_service_list_api_keys.return_value = MagicMock(
        api_keys=[MagicMock(creator_id="user-1", raw_key="existing-key")]
    )

    with patch.object(ApiKeyApi, "resolve_org_context", return_value=org):
        assert ApiKeyApi().get_or_create_default("my-org") == "existing-key"


def test_get_or_create_default_creates_org_key_when_missing(mock_client: MagicMock) -> None:
    org = MagicMock()
    org.id = "org-1"

    mock_client.auth_service_get_user.return_value = MagicMock(id="user-1")
    mock_client.projects_service_list_api_keys.return_value = MagicMock(api_keys=[])
    mock_client.organizations_service_list_org_roles.return_value = MagicMock(roles=[_member_role()])
    mock_client.projects_service_create_api_key.return_value = MagicMock(raw_key="new-key")

    with patch.object(ApiKeyApi, "resolve_org_context", return_value=org):
        assert ApiKeyApi().get_or_create_default("my-org") == "new-key"

    create_body = mock_client.projects_service_create_api_key.call_args.kwargs["body"]
    assert create_body.org_id == "org-1"
    assert create_body.name == "Default"
    assert create_body.role == "role-member"


def test_get_or_create_default_falls_back_to_personal_key(mock_client: MagicMock) -> None:
    mock_client.auth_service_get_user.return_value = MagicMock(id="user-1", api_key="personal-key")

    with patch.object(ApiKeyApi, "resolve_org_context", return_value=None):
        assert ApiKeyApi().get_or_create_default() == "personal-key"


def test_resolve_org_context_uses_user_organization(mock_client: MagicMock) -> None:
    org = MagicMock()
    org.id = "org-1"

    mock_client.auth_service_get_user.return_value = MagicMock(
        organization="lightningai-engineering",
        organizations=[],
    )

    with (
        patch("lightning_sdk.utils.resolve._resolve_org_name", return_value=None),
        patch.object(ApiKeyApi, "_try_resolve_org_by_name", return_value=org) as resolve_name,
    ):
        assert ApiKeyApi().resolve_org_context() is org

    resolve_name.assert_called_once_with("lightningai-engineering")


def test_create_uses_default_description_for_default_name(mock_client: MagicMock) -> None:
    mock_client.organizations_service_list_org_roles.return_value = MagicMock(roles=[_member_role()])
    mock_client.projects_service_create_api_key.return_value = MagicMock(raw_key="new-key")

    ApiKeyApi().create("org-1", "Default")

    create_body = mock_client.projects_service_create_api_key.call_args.kwargs["body"]
    assert create_body.description == "Auto-created for model API access"
