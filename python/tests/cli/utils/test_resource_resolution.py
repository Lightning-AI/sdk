from unittest.mock import MagicMock, patch

import pytest
import rich_click as click

from lightning_sdk.cli.utils.resource_resolution import (
    join_teamspace_slug,
    resolve_cluster,
    resolve_job,
    resolve_mmt,
    resolve_studio,
    resolve_teamspace,
)
from lightning_sdk.lightning_cloud.openapi import V1ClusterType
from lightning_sdk.lightning_cloud.openapi.rest import ApiException


def test_resolve_teamspace_uses_sdk_defaults() -> None:
    resolved = MagicMock()
    with patch(
        "lightning_sdk.cli.utils.resource_resolution._resolve_teamspace",
        return_value=resolved,
    ) as resolve:
        assert resolve_teamspace() is resolved
    resolve.assert_called_once_with(teamspace=None, org=None, user=None)


def test_resolve_teamspace_requires_teamspace_when_sdk_has_no_default() -> None:
    with patch(
        "lightning_sdk.cli.utils.resource_resolution._resolve_teamspace",
        return_value=None,
    ), pytest.raises(click.UsageError, match="--teamspace"):
        resolve_teamspace()


def test_resolve_teamspace_preserves_transport_errors() -> None:
    failure = RuntimeError("service unavailable")
    with patch(
        "lightning_sdk.cli.utils.resource_resolution._resolve_teamspace",
        side_effect=failure,
    ), pytest.raises(RuntimeError, match="service unavailable"):
        resolve_teamspace("owner/teamspace")


def test_resolve_cluster_requires_explicit_or_default_account() -> None:
    teamspace = MagicMock(default_cloud_account=None)

    with pytest.raises(click.UsageError, match="--cloud-account"):
        resolve_cluster(teamspace, None, "--cloud-account")


def test_resolve_cluster_uses_teamspace_default() -> None:
    teamspace = MagicMock(id="ts", default_cloud_account="account")
    resolved = MagicMock(id="cluster")
    resolved.spec.cluster_type = "BYOC"

    with patch("lightning_sdk.cli.utils.resource_resolution.CloudAccountApi") as api:
        api.return_value.get_cloud_account_non_org.return_value = resolved

        assert resolve_cluster(teamspace, None, "--cloud-account") == "cluster"


def test_resolve_cluster_maps_global_account_to_none() -> None:
    teamspace = MagicMock(id="ts", default_cloud_account="account")
    resolved = MagicMock()
    resolved.spec.cluster_type = V1ClusterType.GLOBAL

    with patch("lightning_sdk.cli.utils.resource_resolution.CloudAccountApi") as api:
        api.return_value.get_cloud_account_non_org.return_value = resolved

        assert resolve_cluster(teamspace, None, "--cloud-account") is None


def test_resolve_studio_uses_exact_sdk_lookup() -> None:
    teamspace = MagicMock()
    resolved = MagicMock()
    with patch(
        "lightning_sdk.cli.utils.resource_resolution.Studio",
        return_value=resolved,
    ) as studio:
        assert resolve_studio("dev", teamspace) is resolved
    studio.assert_called_once_with(name="dev", teamspace=teamspace, create_ok=False)


def test_resolve_studio_converts_not_found_to_usage_error() -> None:
    with patch(
        "lightning_sdk.cli.utils.resource_resolution.Studio",
        side_effect=ValueError("Studio 'missing' does not exist."),
    ), pytest.raises(click.UsageError, match="missing"):
        resolve_studio("missing", MagicMock())


def test_resolve_job_requires_name() -> None:
    with pytest.raises(click.UsageError, match="JOB"):
        resolve_job(None, MagicMock())


def test_resolve_job_fetches_exact_name() -> None:
    teamspace = MagicMock()
    resolved = MagicMock()
    with patch(
        "lightning_sdk.cli.utils.resource_resolution.Job",
        return_value=resolved,
    ) as job:
        assert resolve_job("train", teamspace) is resolved
    job.assert_called_once_with(name="train", teamspace=teamspace)


def test_resolve_job_converts_not_found_to_usage_error() -> None:
    with patch(
        "lightning_sdk.cli.utils.resource_resolution.Job",
        side_effect=ValueError("missing"),
    ), pytest.raises(click.UsageError, match="train"):
        resolve_job("train", MagicMock())


def test_resolve_mmt_requires_name() -> None:
    with pytest.raises(click.UsageError, match="JOB"):
        resolve_mmt(None, MagicMock())


def test_resolve_mmt_fetches_exact_name() -> None:
    teamspace = MagicMock()
    resolved = MagicMock()
    with patch(
        "lightning_sdk.cli.utils.resource_resolution.MMT",
        return_value=resolved,
    ) as mmt:
        assert resolve_mmt("distributed", teamspace) is resolved
    mmt.assert_called_once_with(name="distributed", teamspace=teamspace)


def test_resolve_mmt_converts_not_found_to_usage_error() -> None:
    with patch(
        "lightning_sdk.cli.utils.resource_resolution.MMT",
        side_effect=ValueError("missing"),
    ), pytest.raises(click.UsageError, match="distributed"):
        resolve_mmt("distributed", MagicMock())


def test_resolve_mmt_converts_real_lookup_not_found_to_usage_error() -> None:
    teamspace = MagicMock()
    teamspace.id = "teamspace-id"
    with patch("lightning_sdk.mmt._resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.mmt.raise_access_error_if_not_allowed"
    ), patch("lightning_sdk.mmt.CloudAccountApi"), patch(
        "lightning_sdk.mmt.MMTApiV2.get_job_by_name",
        side_effect=ApiException(status=404, reason="Not Found"),
    ), pytest.raises(click.UsageError, match="distributed"):
        resolve_mmt("distributed", teamspace)


def test_resolve_mmt_preserves_pre_lookup_not_found_error() -> None:
    failure = ApiException(status=404, reason="Teamspace Not Found")
    with patch("lightning_sdk.mmt._resolve_teamspace", side_effect=failure), pytest.raises(
        ApiException
    ) as raised:
        resolve_mmt("distributed", MagicMock())

    assert raised.value is failure


def test_resolve_mmt_preserves_real_lookup_permission_error() -> None:
    teamspace = MagicMock()
    teamspace.id = "teamspace-id"
    failure = ApiException(status=403, reason="Forbidden")
    with patch("lightning_sdk.mmt._resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.mmt.raise_access_error_if_not_allowed"
    ), patch("lightning_sdk.mmt.CloudAccountApi"), patch(
        "lightning_sdk.mmt.MMTApiV2.get_job_by_name",
        side_effect=failure,
    ), pytest.raises(ApiException) as raised:
        resolve_mmt("distributed", teamspace)

    assert raised.value is failure


def test_join_teamspace_slug_uses_owner_only_when_both_parts_exist() -> None:
    assert join_teamspace_slug("owner", "teamspace") == "owner/teamspace"
    assert join_teamspace_slug(None, "teamspace") == "teamspace"
    assert join_teamspace_slug("owner", None) is None
