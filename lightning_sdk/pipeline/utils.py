from typing import Any, List, Literal, Optional, Union

from lightning_sdk.lightning_cloud.openapi.models import (
    V1JobSpec,
    V1PipelineStep,
    V1PipelineStepType,
    V1SharedFilesystem,
)
from lightning_sdk.studio import Studio

DEFAULT = "DEFAULT"


def prepare_steps(steps: List["V1PipelineStep"]) -> List["V1PipelineStep"]:
    """The prepare_steps function is responsible for creating dependencies between steps.

    The dependencies are based on whether a step wait_for to be executed before another.
    """
    name_to_step = {}
    name_to_idx = {}

    for current_step_idx, current_step in enumerate(steps):
        if current_step.name not in name_to_step:
            name_to_step[current_step.name] = current_step
            name_to_idx[current_step.name] = current_step_idx
        else:
            raise ValueError(f"A step with the name {current_step.name} already exists.")

    if steps[0].wait_for not in [None, DEFAULT, []]:
        raise ValueError("The first step isn't allowed to receive `wait_for=...`.")

    steps[0].wait_for = []

    # This implements a linear dependency between the steps as the default behaviour
    for current_step_idx, current_step in reversed(list(enumerate(steps))):
        if current_step_idx == 0:
            continue

        if current_step.wait_for == DEFAULT:
            prev_step_idx = current_step_idx - 1
            wait_for = []
            while prev_step_idx > -1:
                prev_step = steps[prev_step_idx]
                wait_for.insert(0, steps[prev_step_idx].name)
                if prev_step.wait_for != []:
                    break
                prev_step_idx -= 1
            current_step.wait_for = wait_for
        else:
            for name in current_step.wait_for:
                if current_step.name == name:
                    raise ValueError(f"You can only reference prior steps. Found {current_step.name}")

                if name not in name_to_step:
                    raise ValueError(f"The step {current_step_idx} doesn't have a valid wait_for. Found {name}")

                if name_to_idx[name] >= name_to_idx[current_step.name]:
                    raise ValueError("You can only reference prior steps")

    return steps


def _get_studio(studio: Union["Studio", str, None]) -> Union[Studio, None]:
    """Resolve a Studio from a name string or return the instance unchanged.

    Args:
        studio: A ``Studio`` instance, a studio name string, or ``None``.

    Returns:
        Union[Studio, None]: The resolved ``Studio`` instance, or ``None``.
    """
    if studio is None:
        return None

    if isinstance(studio, Studio):
        return studio

    return Studio(studio)


def _validate_cloud_account(
    pipeline_cloud_account: str, step_cloud_account: str, shared_filesystem: Union[bool, V1SharedFilesystem]
) -> None:
    """Raise if two cloud account IDs conflict when a shared filesystem is enabled.

    Args:
        pipeline_cloud_account: The pipeline-level cloud account ID (may be empty string).
        step_cloud_account: The step-level cloud account ID (may be empty string).
        shared_filesystem: Whether the shared filesystem is enabled (bool or config object).

    Raises:
        ValueError: If both IDs are non-empty and do not match while shared filesystem is on.
    """
    shared_filesystem_enable = (
        shared_filesystem.enabled if isinstance(shared_filesystem, V1SharedFilesystem) else shared_filesystem
    )
    if not shared_filesystem_enable:
        return

    if pipeline_cloud_account != "" and step_cloud_account != "" and pipeline_cloud_account != step_cloud_account:
        raise ValueError(
            "With shared filesystem enabled, all the pipeline steps requires to be on the same cluster."
            f" Found {pipeline_cloud_account} and {step_cloud_account}"
        )


def _to_wait_for(wait_for: Optional[Union[str, List[str]]]) -> Optional[Union[List[str], Literal["DEFAULT"]]]:
    """Normalise a ``wait_for`` value to a list (or the sentinel ``"DEFAULT"``).

    Args:
        wait_for: A step name, list of step names, ``None``, or the ``DEFAULT`` sentinel.

    Returns:
        Union[List[str], Literal["DEFAULT"]]: An empty list when ``None``, the original list,
        a single-element list when a bare string is given, or the ``DEFAULT`` sentinel.
    """
    if wait_for == DEFAULT:
        return wait_for

    if wait_for is None:
        return []

    return wait_for if isinstance(wait_for, list) else [wait_for]


def _get_cloud_account(steps: List[V1PipelineStep]) -> Optional[str]:
    """Return the cloud account ID used across all steps (sorted first when multiple exist).

    Args:
        steps: The list of pipeline steps to inspect.

    Returns:
        Optional[str]: The selected cloud account ID, or ``None`` if there are no steps.
    """
    if len(steps) == 0:
        return None

    cluster_ids: set[str] = set()
    for step in steps:
        job_spec = _get_spec(step)
        cluster_ids.add(job_spec.cluster_id)

    return sorted(cluster_ids)[0]


def _get_spec(step: Any) -> V1JobSpec:
    """Extract the job spec from a pipeline step, regardless of its step type.

    Args:
        step: A pipeline step proto with a ``type`` attribute and matching payload field.

    Returns:
        V1JobSpec: The job specification embedded in the step.
    """
    if step.type == V1PipelineStepType.DEPLOYMENT:
        return step.deployment.spec
    if step.type == V1PipelineStepType.MMT:
        return step.mmt.spec
    return step.job.spec
