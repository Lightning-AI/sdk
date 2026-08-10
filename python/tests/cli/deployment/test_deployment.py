import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from lightning_sdk.api.logs_api import LogEntry
from lightning_sdk.cli.deployment.create import create_deployment
from lightning_sdk.cli.deployment.list import list_deployments
from lightning_sdk.cli.deployment.logs import deployment_logs
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
from tests.cli.help import assert_help_contains, mock_command_logging


def _unacked_exc(*codes):
    e = ApiException(status=400, reason="Bad Request")
    e.body = json.dumps({"code": 3, "message": "unacknowledged BYOM warnings: " + ", ".join(codes)})
    return e


@mock_command_logging
def test_deployment_help() -> None:
    assert_help_contains(
        "lightning deployment --help",
        "Usage: lightning deployment [OPTIONS] COMMAND [ARGS]...",
        "Deploy autoscaling inference APIs.",
        "create",
        "delete",
        "inspect",
        "list",
        "logs",
        "update",
    )


@mock_command_logging
def test_deployments_alias_help() -> None:
    assert_help_contains(
        "lightning deployments list --help",
        "Usage: lightning deployments list",
        "List deployments in a teamspace.",
    )


@mock_command_logging
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


@mock_command_logging
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


@mock_command_logging
def test_create_deployment_delegates_to_sdk(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id", name="test")
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


@mock_command_logging
def test_create_deployment_with_cloud(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id", name="test")
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


@mock_command_logging
def test_create_deployment_requires_name(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())

    result = CliRunner().invoke(
        create_deployment,
        ["--teamspace", "ecorp/test", "--image", "nginx", "--port", "8000"],
    )

    assert result.exit_code != 0
    assert "Deployment name is required" in result.output


@mock_command_logging
def test_create_deployment_image_requires_port(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())

    result = CliRunner().invoke(create_deployment, ["api", "--image", "nginx"])

    assert result.exit_code != 0
    assert "--port" in result.output
    assert " is required" in result.output


@mock_command_logging
def test_create_deployment_model_mutually_exclusive_with_image(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())

    result = CliRunner().invoke(
        create_deployment,
        ["api", "--image", "nginx", "--model", "meta-llama/Llama-3-8B", "--machine", "L4", "--port", "8000"],
    )

    assert result.exit_code != 0
    output = click.unstyle(result.output)

    assert "Exactly one of --image, --studio, or --model is required." in output


@mock_command_logging
def test_create_deployment_model_requires_gpu(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())

    result = CliRunner().invoke(
        create_deployment,
        ["api", "--model", "meta-llama/Llama-3-8B", "--port", "8000"],
    )

    assert result.exit_code != 0
    assert "GPU machine" in result.output


@mock_command_logging
def test_create_deployment_model_delegates_and_defaults_port(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id", name="test")
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
@mock_command_logging
def test_create_deployment_enable_weight_reload_delegates(monkeypatch, flag, expected) -> None:
    teamspace = SimpleNamespace(id="project-id", name="test")
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


@mock_command_logging
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


@mock_command_logging
def test_create_model_force_acks_and_retries(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id", name="test")
    deployment = MagicMock()
    deployment.name = "llm"
    deployment.start.side_effect = [_unacked_exc("BYOM_INSUFFICIENT_VRAM_ESTIMATE"), None]

    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock(return_value=teamspace))
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.Deployment", MagicMock(return_value=deployment))

    result = CliRunner().invoke(create_deployment, ["llm", "--model", "meta-llama/x", "--machine", "L4", "--force"])

    assert result.exit_code == 0, result.output
    assert deployment.start.call_count == 2
    assert "BYOM_INSUFFICIENT_VRAM_ESTIMATE" in deployment.start.call_args_list[1].kwargs["acknowledged_warnings"]


@mock_command_logging
def test_create_model_non_interactive_unacked_errors(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id", name="test")
    deployment = MagicMock()
    deployment.start.side_effect = _unacked_exc("BYOM_INSUFFICIENT_VRAM_ESTIMATE")

    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock(return_value=teamspace))
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.Deployment", MagicMock(return_value=deployment))

    result = CliRunner().invoke(create_deployment, ["llm", "--model", "meta-llama/x", "--machine", "L4"])

    assert result.exit_code != 0
    assert "unacknowledged warnings" in result.output
    assert "BYOM_INSUFFICIENT_VRAM_ESTIMATE" in result.output


@mock_command_logging
def test_create_model_dry_run_skips_create(monkeypatch) -> None:
    deployment_cls = MagicMock()
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.Deployment", deployment_cls)

    result = CliRunner().invoke(create_deployment, ["llm", "--model", "meta-llama/x", "--machine", "L4", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Dry run" in result.output
    assert "No deployment created" in result.output
    deployment_cls.assert_not_called()


@mock_command_logging
def test_create_ack_without_model_errors(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())

    result = CliRunner().invoke(create_deployment, ["api", "--image", "nginx", "--port", "8000", "--ack", "X"])

    assert result.exit_code != 0
    output = click.unstyle(result.output)
    assert "only supported with --model" in output


@mock_command_logging
def test_create_serving_image_variant_accepted(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id", name="test")
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


@mock_command_logging
def test_create_old_byom_image_variant_rejected(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock())

    result = CliRunner().invoke(
        create_deployment, ["llm", "--model", "meta-llama/x", "--machine", "L4", "--byom-image-variant", "x"]
    )

    assert result.exit_code != 0  # flag renamed to --serving-image-variant


def _patch_logs_command(monkeypatch, api, entries):
    """Wire the deployment logs command to ``api`` and make the logs API yield ``entries``."""
    teamspace = SimpleNamespace(id="project-id", name="test")
    monkeypatch.setattr(
        "lightning_sdk.cli.deployment.logs.resolve_teamspace",
        MagicMock(return_value=teamspace),
    )
    monkeypatch.setattr("lightning_sdk.cli.deployment.logs.DeploymentApi", MagicMock(return_value=api))
    # the command delegates to the shared reader, which owns the API client
    stream = MagicMock(return_value=list(entries))
    monkeypatch.setattr(
        "lightning_sdk.cli.utils.logs.LogsApi",
        MagicMock(return_value=SimpleNamespace(stream=stream, get_page=MagicMock())),
    )
    return stream


def _deployment_api_with_replicas(*names):
    api = MagicMock()
    api.get_deployment_by_name.return_value = V1Deployment(name="my-deployment", id="dep-id", project_id="project-id")
    api.list_deployment_jobs.return_value = [
        V1Job(id=f"job-{i}", name=name, deployment_id="dep-id") for i, name in enumerate(names)
    ]
    return api


@mock_command_logging
def test_deployment_logs_reads_whole_deployment_and_labels_replicas(monkeypatch) -> None:
    api = _deployment_api_with_replicas("replica-0", "replica-1")
    stream = _patch_logs_command(
        monkeypatch,
        api,
        [
            LogEntry(message="ready", resource_id="job-0"),
            LogEntry(message="serving", resource_id="job-1"),
        ],
    )

    result = CliRunner().invoke(deployment_logs, ["my-deployment", "--teamspace", "ecorp/test"])

    assert result.exit_code == 0, result.output
    # one call for every replica, each line labelled with the replica it came from
    assert result.output == "[replica-0] ready\n[replica-1] serving\n"
    kwargs = stream.call_args.kwargs
    assert kwargs["deployment_id"] == "dep-id"
    assert kwargs["job_ids"] == []
    # months of replicas can sit behind a deployment, so a plain read shows the recent tail
    assert kwargs["tail"] == 100


@mock_command_logging
def test_deployment_logs_single_replica_is_not_labelled(monkeypatch) -> None:
    api = _deployment_api_with_replicas("replica-0")
    _patch_logs_command(monkeypatch, api, [LogEntry(message="ready", resource_id="job-0")])

    result = CliRunner().invoke(deployment_logs, ["my-deployment"])

    assert result.exit_code == 0, result.output
    assert result.output == "ready\n"


@mock_command_logging
def test_deployment_logs_selected_job_ids_and_filters(monkeypatch) -> None:
    api = _deployment_api_with_replicas("replica-0", "replica-1")
    stream = _patch_logs_command(monkeypatch, api, [])

    result = CliRunner().invoke(
        deployment_logs,
        [
            "my-deployment",
            "--job-id",
            "job-1",
            "--query",
            "timeout",
            "--severity",
            "error",
            "--since",
            "2026-07-27T00:00:00Z",
            "--follow",
        ],
    )

    assert result.exit_code == 0, result.output
    kwargs = stream.call_args.kwargs
    assert kwargs["job_ids"] == ["job-1"]
    # a fixed job id list replaces the deployment selector
    assert kwargs["deployment_id"] is None
    assert kwargs["query"] == "timeout"
    assert kwargs["severity"] == "error"
    assert kwargs["since"] == "2026-07-27T00:00:00+00:00"
    assert kwargs["follow"] is True
    assert kwargs["idle_timeout"] is None


@mock_command_logging
def test_deployment_logs_rejects_bad_severity(monkeypatch) -> None:
    api = _deployment_api_with_replicas("replica-0")
    _patch_logs_command(monkeypatch, api, [])

    result = CliRunner().invoke(deployment_logs, ["my-deployment", "--severity", "critical"])

    assert result.exit_code != 0
    assert "critical" in result.output


@mock_command_logging
def test_deployment_logs_reports_no_jobs(monkeypatch) -> None:
    api = _deployment_api_with_replicas()
    _patch_logs_command(monkeypatch, api, [])

    result = CliRunner().invoke(deployment_logs, ["my-deployment"])

    assert result.exit_code == 0, result.output
    assert "No jobs found for this deployment." in result.output


@mock_command_logging
def test_deployment_logs_rank_uses_legacy_path(monkeypatch) -> None:
    api = _deployment_api_with_replicas("replica-0")
    api.iter_job_log_entries.return_value = iter([LogEntry(message="from rank 2")])
    _patch_logs_command(monkeypatch, api, [])

    result = CliRunner().invoke(deployment_logs, ["my-deployment", "--rank", "2"])

    assert result.exit_code == 0, result.output
    assert result.output == "from rank 2\n"
    assert api.iter_job_log_entries.call_args.kwargs["rank"] == 2


@mock_command_logging
def test_deployment_logs_rank_needs_a_single_replica(monkeypatch) -> None:
    api = _deployment_api_with_replicas("replica-0", "replica-1")
    _patch_logs_command(monkeypatch, api, [])

    result = CliRunner().invoke(deployment_logs, ["my-deployment", "--rank", "0"])

    assert result.exit_code != 0
    assert "--job-id" in result.output
    api.iter_job_log_entries.assert_not_called()


def _patch_tui_command(monkeypatch, api):
    teamspace = SimpleNamespace(id="project-id", name="test", owner=SimpleNamespace(name="ecorp"))
    monkeypatch.setattr(
        "lightning_sdk.cli.deployment.logs.resolve_teamspace",
        MagicMock(return_value=teamspace),
    )
    monkeypatch.setattr("lightning_sdk.cli.deployment.logs.DeploymentApi", MagicMock(return_value=api))
    run_tui = MagicMock()
    monkeypatch.setattr("lightning_sdk.cli.logs_tui.run_tui", run_tui)
    return run_tui


def _deployment_api_with_specced_replicas(*specs):
    """Build a deployment API whose replicas carry the given ``(name, quantity)`` job specs."""
    api = MagicMock()
    api.get_deployment_by_name.return_value = V1Deployment(name="my-deployment", id="dep-id", project_id="project-id")
    api.list_deployment_jobs.return_value = [
        V1Job(id=f"job-{i}", name=name, deployment_id="dep-id", spec=V1JobSpec(quantity=quantity))
        for i, (name, quantity) in enumerate(specs)
    ]
    return api


@mock_command_logging
def test_deployment_logs_tui_opens_for_multi_node_replica(monkeypatch) -> None:
    api = _deployment_api_with_specced_replicas(("replica-0", 2))
    run_tui = _patch_tui_command(monkeypatch, api)

    result = CliRunner().invoke(deployment_logs, ["my-deployment", "--interactive"])

    assert result.exit_code == 0, result.output
    run_tui.assert_called_once()


@mock_command_logging
def test_deployment_logs_tui_rejects_rank(monkeypatch) -> None:
    api = _deployment_api_with_specced_replicas(("replica-0", 1))
    run_tui = _patch_tui_command(monkeypatch, api)

    result = CliRunner().invoke(deployment_logs, ["my-deployment", "--interactive", "--rank", "1"])

    assert result.exit_code != 0
    output = click.unstyle(result.output)
    assert "TUI view does not support --rank" in output
    assert "lightning deployment logs my-deployment --rank 1" in output
    assert "--interactive" not in output
    run_tui.assert_not_called()


@mock_command_logging
def test_deployment_logs_tui_launches_for_single_node_replicas(monkeypatch) -> None:
    api = _deployment_api_with_specced_replicas(("replica-0", 1), ("replica-1", 1))
    run_tui = _patch_tui_command(monkeypatch, api)

    result = CliRunner().invoke(deployment_logs, ["my-deployment", "--interactive"])

    assert result.exit_code == 0, result.output
    run_tui.assert_called_once()
    selection = run_tui.call_args.args[0]
    assert selection.deployment_id == "dep-id"
    assert selection.labels == {"job-0": "replica-0", "job-1": "replica-1"}


@mock_command_logging
def test_reload_weights_calls_api_and_prints_version(monkeypatch) -> None:
    teamspace = SimpleNamespace(id="project-id", name="test")
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


@mock_command_logging
def test_deployment_logs_help() -> None:
    assert_help_contains(
        "lightning deployment logs --help",
        "Usage: lightning deployment logs",
        "--job-id",
        "--query",
        "--severity",
        "--follow",
        "--tail",
        "--timestamps",
    )


def test_create_deployment_json(monkeypatch) -> None:
    import json
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from click.testing import CliRunner

    from lightning_sdk.cli.deployment.create import create_deployment

    dep = SimpleNamespace(id="dep-1", name="hello-api", urls=["https://80-dep-1-d.cloudspaces.litng.ai"])
    monkeypatch.setattr(
        "lightning_sdk.cli.deployment.create.resolve_teamspace", MagicMock(return_value=SimpleNamespace(id="ts"))
    )
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.resolve_machine", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr("lightning_sdk.cli.deployment.create.create_with_acknowledgement", MagicMock(return_value=dep))

    result = CliRunner().invoke(create_deployment, ["hello-api", "--image", "nginx", "--port", "80", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "id": "dep-1",
        "name": "hello-api",
        "urls": ["https://80-dep-1-d.cloudspaces.litng.ai"],
    }
