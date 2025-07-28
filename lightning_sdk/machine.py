from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Optional, Tuple


class CloudProvider(Enum):
    AWS = "AWS"
    GCP = "GCP"
    VULTR = "VULTR"
    LAMBDA_LABS = "LAMBDA_LABS"
    DGX = "DGX"
    VOLTAGE_PARK = "VOLTAGE_PARK"
    NEBIUS = "NEBIUS"
    LIGHTNING = "LIGHTNING"

    def __str__(self) -> str:
        """Converts the CloudProvider to a str."""
        return self.value


@dataclass(frozen=True)
class Machine:
    # supported CPU variations
    CPU_X_2: ClassVar["Machine"]
    CPU_X_4: ClassVar["Machine"]
    CPU_X_8: ClassVar["Machine"]
    CPU_X_16: ClassVar["Machine"]
    # default CPU machines
    CPU_SMALL: ClassVar["Machine"]
    CPU: ClassVar["Machine"]
    # supported data-prep variations (big disk)
    DATA_PREP: ClassVar["Machine"]
    DATA_PREP_MAX: ClassVar["Machine"]
    DATA_PREP_ULTRA: ClassVar["Machine"]

    # supported GPU types
    # supported T4 variations
    T4: ClassVar["Machine"]
    T4_X_2: ClassVar["Machine"]
    T4_X_4: ClassVar["Machine"]
    T4_X_8: ClassVar["Machine"]
    # supported L4 variations
    L4: ClassVar["Machine"]
    L4_X_2: ClassVar["Machine"]
    L4_X_4: ClassVar["Machine"]
    L4_X_8: ClassVar["Machine"]
    # supported L40S variations
    L40S: ClassVar["Machine"]
    L40S_X_2: ClassVar["Machine"]
    L40S_X_4: ClassVar["Machine"]
    L40S_X_8: ClassVar["Machine"]
    # supported A100 variations
    # defaults, can be either A100 type depending on cloud provider availability
    A100: ClassVar["Machine"]
    A100_X_2: ClassVar["Machine"]
    A100_X_4: ClassVar["Machine"]
    A100_X_8: ClassVar["Machine"]
    # A100 40GB versions
    A100_40GB: ClassVar["Machine"]
    A100_40GB_X_2: ClassVar["Machine"]
    A100_40GB_X_4: ClassVar["Machine"]
    A100_40GB_X_8: ClassVar["Machine"]
    # A100 80GB versions
    A100_80GB: ClassVar["Machine"]
    A100_80GB_X_2: ClassVar["Machine"]
    A100_80GB_X_4: ClassVar["Machine"]
    A100_80GB_X_8: ClassVar["Machine"]

    H100: ClassVar["Machine"]
    H100_X_2: ClassVar["Machine"]
    H100_X_4: ClassVar["Machine"]
    H100_X_8: ClassVar["Machine"]

    H200: ClassVar["Machine"]
    H200_X_8: ClassVar["Machine"]
    B200_X_8: ClassVar["Machine"]

    # Specialized Machines

    name: str
    slug: str
    instance_type: Optional[str] = None
    family: Optional[str] = None
    accelerator_count: Optional[int] = None
    cost: Optional[float] = None
    interruptible_cost: Optional[float] = None
    wait_time: Optional[float] = None
    interruptible_wait_time: Optional[float] = None
    _include_in_cli: bool = True

    def __str__(self) -> str:
        """String representation of the Machine."""
        return str(self.name) if self.name else (self.slug if self.slug else str(self.instance_type))

    def __eq__(self, other: object) -> bool:
        """Machines are equal if the instance type is equal."""
        if isinstance(other, Machine):
            return (
                # equality based on raw instance type (provider specific)
                (self.instance_type and self.instance_type == other.instance_type)
                # equality based on slug (provider agnostic)
                or self.slug == other.slug
                # equality based on machine specs (e.g. A100_80GB_X_8 == A100_X_8)
                or (self.family == other.family and self.accelerator_count == other.accelerator_count)
            )
        return False

    def is_cpu(self) -> bool:
        """Whether the machine is a CPU."""
        return self.family in ("CPU", "DATA_PREP")

    @classmethod
    def from_str(cls, machine: str, *additional_machine_ids: Any) -> "Machine":
        possible_values: Tuple["Machine", ...] = tuple(
            [machine for machine in cls.__dict__.values() if isinstance(machine, cls)]
        )
        for m in possible_values:
            for machine_id in [machine, *additional_machine_ids]:
                if machine_id in (
                    getattr(m, "name", None),
                    getattr(m, "instance_type", None),
                    getattr(m, "slug", None),
                ):
                    return m

        if additional_machine_ids:
            return cls(machine, *additional_machine_ids)
        return cls(machine, machine, machine)


# CPU machines
# default CPU machines
Machine.CPU_SMALL = Machine(name="CPU_SMALL", slug="cpu-2", family="CPU", accelerator_count=2)
Machine.CPU = Machine(name="CPU", slug="cpu-4", family="CPU", accelerator_count=4)
# available CPU variations
Machine.CPU_X_2 = Machine(name="CPU_X_2", slug="cpu-2", family="CPU", accelerator_count=2)
Machine.CPU_X_4 = Machine(name="CPU_X_4", slug="cpu-4", family="CPU", accelerator_count=4)
Machine.CPU_X_8 = Machine(name="CPU_X_8", slug="cpu-8", family="CPU", accelerator_count=8)
Machine.CPU_X_16 = Machine(name="CPU_X_16", slug="cpu-16", family="CPU", accelerator_count=16)
# available data-prep (big disk) machines
Machine.DATA_PREP = Machine(name="DATA_PREP", slug="data-prep-mid", family="DATA_PREP", accelerator_count=32)
Machine.DATA_PREP_MAX = Machine(
    name="DATA_PREP_MAX", slug="data-prep-max-large", family="DATA_PREP", accelerator_count=64
)
Machine.DATA_PREP_ULTRA = Machine(
    name="DATA_PREP_ULTRA", slug="data-prep-ultra-extra-large", family="DATA_PREP", accelerator_count=96
)

# GPU machines
# available T4 machines
Machine.T4 = Machine(name="T4", slug="lit-t4-1", family="T4", accelerator_count=1)
Machine.T4_X_2 = Machine(name="T4_X_2", slug="lit-t4-2", family="T4", accelerator_count=2)
Machine.T4_X_4 = Machine(name="T4_X_4", slug="lit-t4-4", family="T4", accelerator_count=4)
Machine.T4_X_8 = Machine(name="T4_X_8", slug="lit-t4-8", family="T4", accelerator_count=8)
# available L4 machines
Machine.L4 = Machine(name="L4", slug="lit-l4-1", family="L4", accelerator_count=1)
Machine.L4_X_2 = Machine(name="L4_X_2", slug="lit-l4-2", family="L4", accelerator_count=2)
Machine.L4_X_4 = Machine(name="L4_X_4", slug="lit-l4-4", family="L4", accelerator_count=4)
Machine.L4_X_8 = Machine(name="L4_X_8", slug="lit-l4-8", family="L4", accelerator_count=8)
# available L40S machines
Machine.L40S = Machine(name="L40S", slug="lit-l40s-1", family="L40S", accelerator_count=1)
Machine.L40S_X_2 = Machine(name="L40S_X_2", slug="lit-l40s-2", family="L40S", accelerator_count=2)
Machine.L40S_X_4 = Machine(name="L40S_X_4", slug="lit-l40s-4", family="L40S", accelerator_count=4)
Machine.L40S_X_8 = Machine(name="L40S_X_8", slug="lit-l40s-8", family="L40S", accelerator_count=8)
# available A100 Machines
Machine.A100 = Machine(name="A100", slug="lit-a100-1", family="A100", accelerator_count=1)
Machine.A100_X_2 = Machine(name="A100_X_2", slug="lit-a100-2", family="A100", accelerator_count=2)
Machine.A100_X_4 = Machine(name="A100_X_4", slug="lit-a100-4", family="A100", accelerator_count=4)
Machine.A100_X_8 = Machine(name="A100_X_8", slug="lit-a100-8", family="A100", accelerator_count=8)
# don't include variants in cli, only default types that can match for all variants
Machine.A100_40GB = Machine(
    name="A100_40GB", slug="lit-a100-40gb-1", family="A100", accelerator_count=1, _include_in_cli=False
)
Machine.A100_40GB_X_2 = Machine(
    name="A100_40GB_X_2", slug="lit-a100-40gb-2", family="A100", accelerator_count=2, _include_in_cli=False
)
Machine.A100_40GB_X_4 = Machine(
    name="A100_40GB_X_4", slug="lit-a100-40gb-4", family="A100", accelerator_count=4, _include_in_cli=False
)
Machine.A100_40GB_X_8 = Machine(
    name="A100_40GB_X_8", slug="lit-a100-40gb-8", family="A100", accelerator_count=8, _include_in_cli=False
)
Machine.A100_80GB = Machine(
    name="A100_80GB", slug="lit-a100-80gb-1", family="A100", accelerator_count=1, _include_in_cli=False
)
Machine.A100_80GB_X_2 = Machine(
    name="A100_80GB_X_2", slug="lit-a100-80gb-2", family="A100", accelerator_count=2, _include_in_cli=False
)
Machine.A100_80GB_X_4 = Machine(
    name="A100_80GB_X_4", slug="lit-a100-80gb-4", family="A100", accelerator_count=4, _include_in_cli=False
)
Machine.A100_80GB_X_8 = Machine(
    name="A100_80GB_X_8", slug="lit-a100-80gb-8", family="A100", accelerator_count=8, _include_in_cli=False
)
# available H100 machines
Machine.H100 = Machine(name="H100", slug="lit-h100-1", family="H100", accelerator_count=1)
Machine.H100_X_2 = Machine(name="H100_X_2", slug="lit-h100-2", family="H100", accelerator_count=2)
Machine.H100_X_4 = Machine(name="H100_X_4", slug="lit-h100-4", family="H100", accelerator_count=4)
Machine.H100_X_8 = Machine(name="H100_X_8", slug="lit-h100-8", family="H100", accelerator_count=8)
# available H200 machines
Machine.H200 = Machine(name="H200", slug="lit-h200x-1", family="H200", accelerator_count=1)
Machine.H200_X_8 = Machine(name="H200_X_8", slug="lit-h200x-8", family="H200", accelerator_count=8)
# available B200 machines
Machine.B200_X_8 = Machine(name="B200_X_8", slug="lit-b200x-8", family="B200", accelerator_count=8)
