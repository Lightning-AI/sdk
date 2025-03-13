from typing import List

from lightning_sdk.lightning_cloud.openapi.models import V1PipelineStep, V1PipelineStepType

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

    if steps[0].wait_for != DEFAULT:
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

    print()
    print("===== Generated Pipeline =====")
    for step_idx, step in enumerate(steps):
        step_type = ""
        if step.type == V1PipelineStepType.DEPLOYMENT:
            step_type = "Deployment"
        elif step.type == V1PipelineStepType.JOB:
            step_type = "Job"
        else:
            step_type = "MMT"
        wait_for = "nothing" if len(step.wait_for) == 0 else step.wait_for
        print(f"{step_idx} - {step_type}['{step.name}'] wait_for {wait_for}")
    print("===== ================== =====")
    print()

    return steps
