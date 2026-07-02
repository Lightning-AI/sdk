from unittest import mock

import pytest

from lightning_sdk.lightning_cloud.openapi import (
    CloudSpaceServiceCreateCloudSpaceBody,
    Externalv1CloudSpaceInstanceStatus,
    V1CloudSpace,
    V1CloudSpaceInstanceStartupStatus,
    V1Endpoint,
    V1GetCloudSpaceInstanceStatusResponse,
    V1LightningRun,
    V1ListCloudSpacesResponse,
    V1ListEndpointsResponse,
    V1Organization,
    V1Project,
    V1ProjectSettings,
)
from lightning_sdk.studio import Studio


def list_cloudspaces_side_effect(existing_studios):
    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    return _list_cloudspaces_side_effect


@pytest.mark.parametrize(
    ("ports_input", "expected_count", "expected_results"),
    [
        (
            8080,
            1,
            [{"name": None, "port": "8080"}],
        ),
        (
            [8080, 3000],
            2,
            [{"name": None, "port": "8080"}, {"name": None, "port": "3000"}],
        ),
        (
            {"web": 8080, "api": 3000},
            2,
            [
                {"name": "web", "port": "8080"},
                {"name": "api", "port": "3000"},
            ],
        ),
    ],
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.endpoint_service_api.EndpointServiceApi.endpoint_service_create_endpoint",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch("requests.put", autospec=True)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_add_port(
    mock_get_teamspace,
    mock_get_org,
    mock_requests_put,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_get_status,
    mock_create_endpoint,
    ports_input,
    expected_count,
    expected_results,
):
    existing_studios = {
        "st-ghi": V1CloudSpace(
            name="st-ghi", display_name="st-ghi", cluster_id="c-abc", project_id="ts-abc", id="st-ghi"
        ),
    }

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id,
            cloudspace_id=cloudspace_id,
            project_id=project_id,
            id=cloudspace_id + "_run",
        )

    def _create_endpoint_side_effect(*args, **kwargs):
        body = kwargs.get("body")
        port = body.ports[0]
        name = body.name
        return V1Endpoint(
            name=name,
            ports=[port],
            urls=[f"https://example.com:{port}"],
        )

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="c-abc", start_studio_on_spot_instance=True),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )
    mock_create_endpoint.side_effect = _create_endpoint_side_effect

    studio = Studio("st-ghi", "ts-abc", "org-abc")
    endpoints = studio.add_ports(ports_input)

    assert len(endpoints) == expected_count
    assert mock_create_endpoint.call_count == expected_count

    for expected in expected_results:
        matching_endpoint = next(
            (ep for ep in endpoints if ep.name == expected["name"] and ep.ports == [expected["port"]]),
            None,
        )
        assert matching_endpoint is not None, f"Expected endpoint with name={expected['name']}, port={expected['port']}"
        assert matching_endpoint.urls == [f"https://example.com:{expected['port']}"]


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.endpoint_service_api.EndpointServiceApi.endpoint_service_list_endpoints",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_list_ports(
    mock_get_teamspace,
    mock_get_org,
    mock_list_cloudspaces,
    mock_get_status,
    mock_list_endpoints,
):
    existing_studios = {
        "st-ghi": V1CloudSpace(
            name="st-ghi", display_name="st-ghi", cluster_id="c-abc", project_id="ts-abc", id="st-ghi"
        ),
    }

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="c-abc", start_studio_on_spot_instance=True),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )

    mock_list_endpoints.return_value = V1ListEndpointsResponse(
        [
            V1Endpoint(name="web", ports=[8080], urls=["https://example.com:8080"]),
            V1Endpoint(name="api", ports=[3000], urls=["https://example.com:3000"]),
            V1Endpoint(name=None, ports=[5000], urls=["https://example.com:5000"]),
        ]
    )

    studio = Studio("st-ghi", "ts-abc", "org-abc")
    endpoints = studio.list_ports()

    assert len(endpoints) == 3
    assert endpoints[0].name == "web"
    assert endpoints[0].ports == [8080]
    assert endpoints[0].urls == ["https://example.com:8080"]
    assert endpoints[1].name == "api"
    assert endpoints[1].ports == [3000]
    assert endpoints[1].urls == ["https://example.com:3000"]
    assert endpoints[2].name is None
    assert endpoints[2].ports == [5000]
    assert endpoints[2].urls == ["https://example.com:5000"]

    mock_list_endpoints.assert_called_once_with(
        mock.ANY,
        project_id="ts-abc",
        cloudspace_id="st-ghi",
    )
