from typing import List

from lightning_sdk.lightning_cloud.openapi.models import V1PipelineStep

NEEDS_DEFAULT = "DEFAULT"


def prepare_steps(steps: List["V1PipelineStep"]) -> List["V1PipelineStep"]:
    """The prepare_steps function is responsible for creating dependencies between steps.

    The dependencies are based on whether a step needs to be executed before another.
    """
    name_to_step = {}
    name_to_idx = {}

    for step_idx, step in enumerate(steps):
        if step.name not in name_to_step:
            name_to_step[step.name] = step
            name_to_idx[step.name] = step_idx
        else:
            raise ValueError(f"A step with the name {step.name} already exists.")

    # This implements a linear dependency between the steps as the default behaviour
    for step_idx, step in enumerate(steps):
        # Overidde the first step with its default behaviour
        if step_idx == 0:
            if step.required != [NEEDS_DEFAULT]:
                raise ValueError("The first step isn't allowed to receive `needs=...`.")

            step.required = []
            continue

        if step.required == [NEEDS_DEFAULT]:
            step.required = [steps[step_idx - 1].name]
        elif step.required is None or step.required == [None]:
            step.required = []
        else:
            for name in step.required:
                if step.name == name:
                    raise ValueError("You can only reference prior steps")

                if name not in name_to_step:
                    raise ValueError(f"The step {step_idx} doesn't have a valid needs. Found {name}")

                if name_to_idx[name] >= name_to_idx[step.name]:
                    raise ValueError("You can only reference prior steps")

    return steps
