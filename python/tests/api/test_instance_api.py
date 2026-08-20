from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from lightning_sdk.api.instance_api import InstanceApi, _error_message, _instance_api_errors
from lightning_sdk.lightning_cloud.openapi import V1Instance
from lightning_sdk.lightning_cloud.openapi.rest import ApiException


@pytest.fixture()
def api():
    """An :class:`InstanceApi` whose generated client is a mock."""
    with mock.patch("lightning_sdk.api.instance_api.cached_lightning_client") as client:
        yield InstanceApi(), client.return_value


def _api_exception(status: int, body: str) -> ApiException:
    exc = ApiException(status=status, reason="reason")
    exc.body = body.encode()
    return exc


def test_error_message_prefers_server_message():
    assert _error_message(_api_exception(400, '{"code":3, "message":"org id is required"}')) == "org id is required"


def test_error_message_falls_back_to_body_then_reason():
    assert _error_message(_api_exception(500, "boom")) == "boom"
    assert _error_message(ApiException(status=500, reason="Server Error")) == "Server Error"


@pytest.mark.parametrize(
    ("status", "expected_type", "expected_message"),
    [
        (501, RuntimeError, "Not supported by Lightning yet: cloud_init is not yet supported"),
        (403, PermissionError, "Not allowed to manage instances: cloud_init is not yet supported"),
        (404, ValueError, "cloud_init is not yet supported"),
        (500, RuntimeError, "Lightning API error 500: cloud_init is not yet supported"),
    ],
)
def test_instance_api_errors_are_mapped(status, expected_type, expected_message):
    with pytest.raises(expected_type, match=expected_message), _instance_api_errors():
        raise _api_exception(status, '{"code":12, "message":"cloud_init is not yet supported"}')


def test_create_instance_builds_request(api):
    instance_api, client = api
    client.cloud_instances_service_create_instance.return_value = V1Instance(id="i-1")

    instance_api.create_instance(
        name="vm",
        organization_id="org-1",
        cloud_account="lightning-baremetal",
        instance_type="cpu-4",
        volume_size=500,
        spot=True,
        ports=[8080, 9090],
        image="ubuntu-24.04",
        cloud_init="#cloud-config\n",
    )

    body = client.cloud_instances_service_create_instance.call_args.kwargs["body"]
    assert body.name == "vm"
    assert body.organization_id == "org-1"
    assert body.cluster_id == "lightning-baremetal"
    assert body.instance_type == "cpu-4"
    # int64 fields go over the wire as strings, ports as a list of strings
    assert body.volume_size == "500"
    assert body.ports == ["8080", "9090"]
    assert body.spot is True
    assert body.image == "ubuntu-24.04"
    assert body.cloud_init == "#cloud-config\n"


def test_create_instance_omits_unset_optional_fields(api):
    instance_api, client = api
    client.cloud_instances_service_create_instance.return_value = V1Instance(id="i-1")

    instance_api.create_instance(
        name="vm",
        organization_id="org-1",
        cloud_account="lightning-baremetal",
        instance_type="cpu-4",
    )

    body = client.cloud_instances_service_create_instance.call_args.kwargs["body"]
    assert body.volume_size is None
    assert body.ports is None
    assert body.image is None
    assert body.cloud_init is None


def test_list_instances_follows_pagination(api):
    instance_api, client = api
    client.cloud_instances_service_list_instances.side_effect = [
        SimpleNamespace(instances=[V1Instance(id="i-1")], next_page_token="page-2"),
        SimpleNamespace(instances=[V1Instance(id="i-2")], next_page_token=""),
    ]

    instances = instance_api.list_instances(organization_id="org-1", limit=1)

    assert [i.id for i in instances] == ["i-1", "i-2"]
    first, second = client.cloud_instances_service_list_instances.call_args_list
    assert first.kwargs == {"organization_id": "org-1", "limit": "1"}
    assert second.kwargs == {"organization_id": "org-1", "limit": "1", "page_token": "page-2"}


def test_list_instances_stops_when_a_page_repeats_its_token(api):
    instance_api, client = api
    client.cloud_instances_service_list_instances.return_value = SimpleNamespace(
        instances=[],
        next_page_token="same-token",
    )

    assert instance_api.list_instances(organization_id="org-1") == []
    assert client.cloud_instances_service_list_instances.call_count == 1


def test_list_instance_images_returns_images_and_default(api):
    instance_api, client = api
    client.cloud_instances_service_list_instance_images.return_value = SimpleNamespace(
        images=[SimpleNamespace(name="ubuntu-24.04", description="Ubuntu")],
        default_image="ubuntu-24.04",
    )

    images, default_image = instance_api.list_instance_images(organization_id="org-1", cloud_account="acct")

    assert [i.name for i in images] == ["ubuntu-24.04"]
    assert default_image == "ubuntu-24.04"
    assert client.cloud_instances_service_list_instance_images.call_args.kwargs == {
        "organization_id": "org-1",
        "cluster_id": "acct",
    }


def test_list_instance_cloud_accounts_keeps_only_machine_clusters(api):
    instance_api, client = api
    client.cluster_service_list_clusters.return_value = SimpleNamespace(
        clusters=[
            SimpleNamespace(id="lightning-baremetal", spec=SimpleNamespace(driver="MACHINE")),
            SimpleNamespace(id="lightning-public-prod", spec=SimpleNamespace(driver="AWS")),
            SimpleNamespace(id="no-spec", spec=None),
        ]
    )

    assert instance_api.list_instance_cloud_accounts() == ["lightning-baremetal"]


def test_list_instance_types_sorts_by_cost_and_skips_disabled(api):
    instance_api, client = api
    client.cluster_service_list_cluster_accelerators.return_value = SimpleNamespace(
        accelerator=[
            SimpleNamespace(
                instance_id="lit-t4-1",
                display_name="T4",
                cost=0.43,
                enabled=True,
                resources=SimpleNamespace(gpu=1, cpu=8, memory_mb="32000"),
            ),
            SimpleNamespace(
                instance_id="cpu-4",
                display_name="Default (CPU)",
                cost=0.33,
                enabled=True,
                resources=SimpleNamespace(gpu=0, cpu=4, memory_mb="16000"),
            ),
            SimpleNamespace(
                instance_id="retired",
                display_name="Retired",
                cost=0.01,
                enabled=False,
                resources=SimpleNamespace(gpu=0, cpu=1, memory_mb="1000"),
            ),
        ]
    )

    types = instance_api.list_instance_types(organization_id="org-1", cloud_account="lightning-baremetal")

    assert types == [
        ("cpu-4", "4 CPU, 16 GB RAM", 0.33),
        ("lit-t4-1", "1x T4, 8 CPU, 32 GB RAM", 0.43),
    ]


def test_delete_instance_passes_org_scope(api):
    instance_api, client = api

    instance_api.delete_instance(instance_id="i-1", organization_id="org-1")

    assert client.cloud_instances_service_delete_instance.call_args.kwargs == {
        "id": "i-1",
        "organization_id": "org-1",
    }
