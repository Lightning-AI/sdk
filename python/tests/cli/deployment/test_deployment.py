import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from lightning_sdk.cli.deployment.create import create_deployment
from lightning_sdk.cli.deployment.list import list_deployments
from lightning_sdk.cli.deployment.logs import _follow_url, _print_page_text, _resolve_jobs, _websocket_url
from lightning_sdk.cli.deployment.reload_weights import reload_weights
from lightning_sdk.lightning_cloud.openapi import (
    V1BYOMSpec,
    V1Deployment,
    V1DeploymentStatus,
    V1Job,
    V1JobSpec,
    V1ReloadDeploymentWeightsResponse,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from tests.cli.help import assert_help_contains


def _unacked_exc(*codes):
    e = ApiException(status=400, reason="Bad Request")
    e.body = json.dumps({"code": 3, "message": "unacknowledged BYOM warnings: " + ", ".join(codes)})
    return e


def test_deployment_help() -> None:
    assert_help_contains(
        "lightning deployment --help",
        "Usage: lightning deployment [OPTIONS] COMMAND [ARGS]...",
        "Manage Lightning AI Deployments.",
        "create",
        "delete",
        "inspect",
        "list",
        "logs",
        "update",
    )


def test_deployments_alias_help() -> None:
    assert_help_contains(
        "lightning deployments list --help",
        "Usage: lightning deployments list",
        "List deployments in a teamspace.",
    )


def test_list_deployments_includes_replicas(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id", name="test", owner=SimpleNamespace(name="ecorp"))
    deployment = V1Deployment(
        name="api",
        id="dep-id",
        replicas=2,
        status=V1DeploymentStatus(ready_replicas=1, pending_replicas=1, failing_replicas=0),
        spec=V1JobSpec(instance_name="CPU", image="nginx", cluster_id="cluster-id"),
    )
    api = MagicMock()
    api.list_deployments.return_value = [deployment]

    monkeypatch.setattr(
        "lightning_sdk.cli.deployment.list.iter_teamspaces",
        lambda teamspace_arg, all_teamspaces: [teamspace],
    )
    monkeypatch.setattr("lightning_sdk.cli.deployment.list.DeploymentApi", MagicMock(return_value=api))

    result = CliRunner().invoke(list_deployments, ["--teamspace", "ecorp/test"])

    assert result.exit_code == 0
    assert "api" in result.output
    assert "1/2" in result.output
    assert "Replicas" in result.output


def test_list_deployments_source_column(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id", name="test", owner=SimpleNamespace(name="ecorp"))
    byom_dep = V1Deployment(
        name="srv",
        id="dep-1",
        replicas=1,
        status=V1DeploymentStatus(ready_replicas=1),
        spec=V1JobSpec(instance_name="L4"),
        byom_spec=V1BYOMSpec(served_model_name="tllm"),
    )
    image_dep = V1Deployment(
        name="ngx",
        id="dep-2",
        replicas=1,
        status=V1DeploymentStatus(ready_replicas=1),
        spec=V1JobSpec(instance_name="CPU", image="nginx"),
    )
    studio_dep = V1Deployment(
        name="std",
        id="dep-3",
        replicas=1,
        status=V1DeploymentStatus(ready_replicas=1),
        cloudspace_id="cs-9",
        spec=V1JobSpec(instance_name="CPU"),
    )
    api = MagicMock()
    api.list_deployments.return_value = [byom_dep, image_dep, studio_dep]

    monkeypatch.setattr(
        "lightning_sdk.cli.deployment.list.iter_teamspaces",
        lambda teamspace_arg, all_teamspaces: [teamspace],
    )
    monkeypatch.setattr("lightning_sdk.cli.deployment.list.DeploymentApi", MagicMock(return_value=api))

    result = CliRunner().invoke(list_deployments, ["--teamspace", "ecorp/test"])

    assert result.exit_code == 0
    assert "Source" in result.output
    assert "model:tllm" in result.output
    assert "image:nginx" in result.output
    assert "studio:cs-9" in result.output


def test_create_deployment_delegates_to_sdk(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id")
    deployment = MagicMock()
    deployment.name = "api"
    deployment_cls = MagicMock(return_value=deployment)

    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock(return_value=teamspace))
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.Deployment", deployment_cls)

    result = CliRunner().invoke(
        create_deployment,
        ["api", "--teamspace", "ecorp/test", "--image", "nginx", "--port", "8000", "--replicas", "2"],
    )

    assert result.exit_code == 0
    deployment_cls.assert_called_once_with(name="api", teamspace=teamspace)
    _, kwargs = deployment.start.call_args
    assert kwargs["image"] == "nginx"
    assert kwargs["ports"] == [8000]
    assert kwargs["replicas"] == 2


def test_create_deployment_with_cloud(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id")
    deployment = MagicMock()
    deployment.name = "api"
    deployment_cls = MagicMock(return_value=deployment)

    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock(return_value=teamspace))
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.Deployment", deployment_cls)

    result = CliRunner().invoke(
        create_deployment,
        ["api", "--teamspace", "ecorp/test", "--image", "nginx", "--port", "8000", "--cloud", "aws"],
    )

    assert result.exit_code == 0, result.output
    assert deployment.start.call_args.kwargs["cloud"] == "aws"


def test_create_deployment_requires_name(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())

    result = CliRunner().invoke(
        create_deployment,
        ["--teamspace", "ecorp/test", "--image", "nginx", "--port", "8000"],
    )

    assert result.exit_code != 0
    assert "Deployment name is required" in result.output


def test_create_deployment_image_requires_port(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())

    result = CliRunner().invoke(create_deployment, ["api", "--image", "nginx"])

    assert result.exit_code != 0
    assert "--port is required" in result.output


def test_create_deployment_model_mutually_exclusive_with_image(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())

    result = CliRunner().invoke(
        create_deployment,
        ["api", "--image", "nginx", "--model", "meta-llama/Llama-3-8B", "--machine", "L4", "--port", "8000"],
    )

    assert result.exit_code != 0
    assert "Exactly one of --image, --studio, or --model" in result.output


def test_create_deployment_model_requires_gpu(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())

    result = CliRunner().invoke(
        create_deployment,
        ["api", "--model", "meta-llama/Llama-3-8B", "--port", "8000"],
    )

    assert result.exit_code != 0
    assert "GPU machine" in result.output


def test_create_deployment_model_delegates_and_defaults_port(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id")
    deployment = MagicMock()
    deployment.name = "llama"
    deployment_cls = MagicMock(return_value=deployment)

    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock(return_value=teamspace))
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.Deployment", deployment_cls)

    result = CliRunner().invoke(
        create_deployment,
        [
            "llama",
            "--model",
            "meta-llama/Llama-3-8B",
            "--machine",
            "L4",
            "--tensor-parallel-size",
            "4",
            "--max-model-len",
            "8192",
            "--quantization",
            "fp8",
            "--vllm-arg",
            "--enable-chunked-prefill",
        ],
    )

    assert result.exit_code == 0, result.output
    _, kwargs = deployment.start.call_args
    assert kwargs["model"] == "meta-llama/Llama-3-8B"
    assert kwargs["tensor_parallel_size"] == 4
    assert kwargs["max_model_len"] == 8192
    assert kwargs["quantization"] == "fp8"
    assert kwargs["extra_vllm_args"] == ["--enable-chunked-prefill"]
    assert kwargs["ports"] == [8000]  # vLLM default, no --port given


@pytest.mark.parametrize(
    ("flag", "expected"),
    [
        ("--enable-weight-reload", True),
        ("--no-enable-weight-reload", False),
        (None, None),
    ],
)
def test_create_deployment_enable_weight_reload_delegates(monkeypatch, flag, expected) -> None:
    teamspace = SimpleNamespace(id="project-id")
    deployment = MagicMock()
    deployment.name = "llama"

    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock(return_value=teamspace))
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.Deployment", MagicMock(return_value=deployment))

    args = ["llama", "--model", "meta-llama/Llama-3-8B", "--machine", "L4"]
    if flag is not None:
        args.append(flag)

    result = CliRunner().invoke(create_deployment, args)

    assert result.exit_code == 0, result.output
    _, kwargs = deployment.start.call_args
    assert kwargs["enable_weight_reload"] is expected


def test_create_deployment_enable_weight_reload_in_dry_run(monkeypatch) -> None:
    deployment_cls = MagicMock()
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.Deployment", deployment_cls)

    result = CliRunner().invoke(
        create_deployment,
        ["llm", "--model", "meta-llama/x", "--machine", "L4", "--enable-weight-reload", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert '"enable_weight_reload": true' in result.output
    deployment_cls.assert_not_called()


def test_create_model_force_acks_and_retries(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id")
    deployment = MagicMock()
    deployment.name = "llm"
    deployment.start.side_effect = [_unacked_exc("BYOM_INSUFFICIENT_VRAM_ESTIMATE"), None]

    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock(return_value=teamspace))
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.Deployment", MagicMock(return_value=deployment))

    result = CliRunner().invoke(create_deployment, ["llm", "--model", "meta-llama/x", "--machine", "L4", "--force"])

    assert result.exit_code == 0, result.output
    assert deployment.start.call_count == 2
    assert "BYOM_INSUFFICIENT_VRAM_ESTIMATE" in deployment.start.call_args_list[1].kwargs["acknowledged_warnings"]


def test_create_model_non_interactive_unacked_errors(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id")
    deployment = MagicMock()
    deployment.start.side_effect = _unacked_exc("BYOM_INSUFFICIENT_VRAM_ESTIMATE")

    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock(return_value=teamspace))
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.Deployment", MagicMock(return_value=deployment))

    result = CliRunner().invoke(create_deployment, ["llm", "--model", "meta-llama/x", "--machine", "L4"])

    assert result.exit_code != 0
    assert "unacknowledged warnings" in result.output
    assert "BYOM_INSUFFICIENT_VRAM_ESTIMATE" in result.output


def test_create_model_dry_run_skips_create(monkeypatch) -> None:
    deployment_cls = MagicMock()
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.Deployment", deployment_cls)

    result = CliRunner().invoke(create_deployment, ["llm", "--model", "meta-llama/x", "--machine", "L4", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Dry run" in result.output
    assert "No deployment created" in result.output
    deployment_cls.assert_not_called()


def test_create_ack_without_model_errors(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())

    result = CliRunner().invoke(create_deployment, ["api", "--image", "nginx", "--port", "8000", "--ack", "X"])

    assert result.exit_code != 0
    assert "only supported with --model" in result.output


def test_create_serving_image_variant_accepted(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id")
    deployment = MagicMock()
    deployment.name = "llm"
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock(return_value=teamspace))
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.Deployment", MagicMock(return_value=deployment))

    result = CliRunner().invoke(
        create_deployment,
        ["llm", "--model", "meta-llama/x", "--machine", "L4", "--serving-image-variant", "nightly"],
    )

    assert result.exit_code == 0, result.output
    assert deployment.start.call_args.kwargs["base_image_variant"] == "nightly"


def test_create_old_byom_image_variant_rejected(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())

    result = CliRunner().invoke(
        create_deployment, ["llm", "--model", "meta-llama/x", "--machine", "L4", "--byom-image-variant", "x"]
    )

    assert result.exit_code != 0  # flag renamed to --serving-image-variant


def test_follow_url_preserves_existing_query() -> None:
    url = _follow_url(
        "/v1/projects/project-id/jobs/job-id/logs?token=abc",
        "project-id",
        "job-id",
        follow=True,
        rank=3,
        tail=50,
    )

    assert url.startswith("/v1/projects/project-id/jobs/job-id/logs?")
    assert "token=abc" in url
    assert "follow=true" in url
    assert "deploymentId" not in url
    assert "rank=3" in url
    assert "tail=50" in url


def test_websocket_url_preserves_absolute_wss_url() -> None:
    url = _websocket_url("wss://lightning.ai/v1/projects/project-id/jobs/job-id/logs?follow=true")

    assert url == "wss://lightning.ai/v1/projects/project-id/jobs/job-id/logs?follow=true"


def test_print_page_text_renders_json_log_entries(capsys) -> None:
    job = SimpleNamespace(id="job-id", name="replica-0")

    rendered = _print_page_text(job, '[{"message":"ready"},{"Message":"serving"}]', prefix=False)
    empty = _print_page_text(job, "[]", prefix=False)

    assert rendered == 2
    assert empty == 0
    assert capsys.readouterr().out == "ready\nserving\n"


def test_reload_weights_calls_api_and_prints_version(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id")
    deployment = V1Deployment(name="my-llama-deployment", id="dep-id", project_id="project-id")
    api = MagicMock()
    api.get_deployment_by_name.return_value = deployment
    api.reload_weights.return_value = V1ReloadDeploymentWeightsResponse(weight_version="3", reload_type="in_place")

    monkeypatch.setattr(
        "lightning_sdk.cli.deployment.reload_weights.resolve_teamspace",
        MagicMock(return_value=teamspace),
    )
    monkeypatch.setattr("lightning_sdk.cli.deployment.reload_weights.DeploymentApi", MagicMock(return_value=api))

    result = CliRunner().invoke(reload_weights, ["my-llama-deployment", "--teamspace", "ecorp/test"])

    assert result.exit_code == 0, result.output
    assert "Weights reloaded (version 3)" in result.output
    api.get_deployment_by_name.assert_called_once_with("my-llama-deployment", "project-id")
    api.reload_weights.assert_called_once_with(deployment)


def test_resolve_jobs_filters_specific_job_id() -> None:
    api = MagicMock()
    api.list_deployment_jobs.return_value = [
        V1Job(id="job-1", name="replica-0", deployment_id="dep-id"),
        V1Job(id="job-2", name="replica-1", deployment_id="dep-id"),
    ]

    jobs = _resolve_jobs(api, "project-id", "dep-id", ["job-2"])

    assert [job.id for job in jobs] == ["job-2"]
