from typing import Dict, Optional, Set

import click

from lightning_sdk.machine import DEFAULT_MACHINE, Machine


def _split_gpus_spec(gpus: str) -> tuple[str, int]:
    machine_name, machine_val = gpus.split(":", 1)
    machine_name = machine_name.strip()
    machine_val = machine_val.strip()

    if not machine_val.isdigit() or int(machine_val) <= 0:
        raise ValueError(f"Invalid GPU count '{machine_val}'. Must be a positive integer.")

    machine_num = int(machine_val)
    return machine_name, machine_num


def _construct_available_gpus(machine_options: Dict[str, str]) -> Set[str]:
    # returns available gpus:count
    available_gpus = set()
    for v in machine_options.values():
        if "_X_" in v:
            gpu_type_num = v.replace("_X_", ":")
            available_gpus.add(gpu_type_num)
        else:
            available_gpus.add(v)
    return available_gpus


def _get_machine_from_gpus(gpus: str) -> Machine:
    machine_name = gpus
    machine_num = 1

    if ":" in gpus:
        machine_name, machine_num = _split_gpus_spec(gpus)

    machine_options = {
        m.name.lower(): m.name for m in Machine.__dict__.values() if isinstance(m, Machine) and m._include_in_cli
    }

    if machine_num == 1:
        # e.g. gpus=L4 or gpus=L4:1
        gpu_key = machine_name.lower()
        try:
            return machine_options[gpu_key]
        except KeyError:
            available = ", ".join(_construct_available_gpus(machine_options))
            raise ValueError(f"Invalid GPU type '{machine_name}'. Available options: {available}") from None

    # Else: e.g. gpus=L4:4
    gpu_key = f"{machine_name.lower()}_x_{machine_num}"
    try:
        return machine_options[gpu_key]
    except KeyError:
        available = ", ".join(_construct_available_gpus(machine_options))
        raise ValueError(f"Invalid GPU configuration '{gpus}'. Available options: {available}") from None


def handle_machine_and_gpus_args(machine: Optional[str], gpus: Optional[str]) -> str:
    if machine and gpus:
        raise click.UsageError("Options --machine and --gpus are mutually exclusive. Provide only one.")
    elif gpus:
        machine = _get_machine_from_gpus(gpus.strip())
    elif not machine:
        machine = DEFAULT_MACHINE

    return machine
