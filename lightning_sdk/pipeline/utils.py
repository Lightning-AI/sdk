from typing import List

from lightning_sdk.lightning_cloud.openapi.models import V1PipelineStep

DEFAULT = "DEFAULT"


def prepare_steps(steps: List["V1PipelineStep"]) -> List["V1PipelineStep"]:
    """The prepare_steps function is responsible for creating dependencies between steps.

    The dependencies are based on whether a step needs to be executed before another.
    """
    name_to_step = {}
    name_to_idx = {}

    for current_step_idx, current_step in enumerate(steps):
        if current_step.name not in name_to_step:
            name_to_step[current_step.name] = current_step
            name_to_idx[current_step.name] = current_step_idx
        else:
            raise ValueError(f"A step with the name {current_step.name} already exists.")

    if steps[0].needs != DEFAULT:
        raise ValueError("The first step isn't allowed to receive `needs=...`.")

    steps[0].needs = []

    # This implements a linear dependency between the steps as the default behaviour
    for current_step_idx, current_step in reversed(list(enumerate(steps))):
        if current_step_idx == 0:
            continue

        if current_step.needs == DEFAULT:
            prev_step_idx = current_step_idx - 1
            needs = []
            while prev_step_idx > -1:
                prev_step = steps[prev_step_idx]
                needs.insert(0, steps[prev_step_idx].name)
                if prev_step.needs != []:
                    break
                prev_step_idx -= 1
            current_step.needs = needs
        elif current_step.needs == []:
            prev_step_idx = current_step_idx - 1
            needs = []
            while prev_step_idx > -1:
                prev_step = steps[prev_step_idx]
                if prev_step.needs != []:
                    break
                prev_step_idx -= 1
            current_step.needs = [] if prev_step_idx == -1 else [prev_step.name]
        else:
            for name in current_step.needs:
                if current_step.name == name:
                    raise ValueError("You can only reference prior steps")

                if name not in name_to_step:
                    raise ValueError(f"The step {current_step_idx} doesn't have a valid needs. Found {name}")

                if name_to_idx[name] >= name_to_idx[current_step.name]:
                    raise ValueError("You can only reference prior steps")
    return steps
