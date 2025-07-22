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


@dataclass(frozen=True)
class Machine:
    # Default Machines
    CPU: ClassVar["Machine"]
    CPU_SMALL: ClassVar["Machine"]
    DATA_PREP: ClassVar["Machine"]
    DATA_PREP_MAX: ClassVar["Machine"]
    DATA_PREP_ULTRA: ClassVar["Machine"]
    T4: ClassVar["Machine"]
    T4_X_4: ClassVar["Machine"]
    L4: ClassVar["Machine"]
    L4_X_2: ClassVar["Machine"]
    L4_X_4: ClassVar["Machine"]
    L4_X_8: ClassVar["Machine"]
    A10G: ClassVar["Machine"]
    A10G_X_4: ClassVar["Machine"]
    A10G_X_8: ClassVar["Machine"]
    L40S: ClassVar["Machine"]
    L40S_X_4: ClassVar["Machine"]
    L40S_X_8: ClassVar["Machine"]
    A100_X_2: ClassVar["Machine"]
    A100_X_4: ClassVar["Machine"]
    A100_X_8: ClassVar["Machine"]
    B200_X_8: ClassVar["Machine"]
    H100_X_8: ClassVar["Machine"]
    H200_X_8: ClassVar["Machine"]

    name: str
    instance_type: str
    cost: Optional[float] = None
    interruptible_cost: Optional[float] = None
    wait_time: Optional[float] = None
    interruptible_wait_time: Optional[float] = None

    def __str__(self) -> str:
        """String representation of the Machine."""
        return str(self.name) if self.name else str(self.instance_type)

    def __eq__(self, other: object) -> bool:
        """Machines are equal if the instance type is equal."""
        if isinstance(other, Machine):
            return self.instance_type == other.instance_type
        return False

    def is_cpu(self) -> bool:
        """Whether the machine is a CPU."""
        return (
            self == Machine.CPU
            or self == Machine.CPU_SMALL
            or self == Machine.DATA_PREP
            or self == Machine.DATA_PREP_MAX
            or self == Machine.DATA_PREP_ULTRA
        )

    @classmethod
    def from_str(cls, machine: str, *additional_machine_ids: Any) -> "Machine":
        possible_values: Tuple["Machine", ...] = tuple(
            [machine for machine in cls.__dict__.values() if isinstance(machine, cls)]
        )
        for m in possible_values:
            for machine_id in [machine, *additional_machine_ids]:
                if machine_id in (getattr(m, "name", None), getattr(m, "instance_type", None)):
                    return m

        if additional_machine_ids:
            return cls(machine, *additional_machine_ids)
        return cls(machine, machine)


Machine.CPU = Machine(name="CPU", instance_type="cpu-4")
Machine.CPU_SMALL = Machine(name="CPU_SMALL", instance_type="n2d-standard-2")  # GCP
Machine.DATA_PREP = Machine(name="DATA_PREP", instance_type="data-large")
Machine.DATA_PREP_MAX = Machine(name="DATA_PREP_MAX", instance_type="data-max")
Machine.DATA_PREP_ULTRA = Machine(name="DATA_PREP_ULTRA", instance_type="data-ultra")
Machine.T4 = Machine(name="T4", instance_type="g4dn.2xlarge")
Machine.T4_X_4 = Machine(name="T4_X_4", instance_type="g4dn.12xlarge")
Machine.L4 = Machine(name="L4", instance_type="g6.4xlarge")
Machine.L4_X_2 = Machine(name="L4_X_2", instance_type="g2-standard-24")  # GCP
Machine.L4_X_4 = Machine(name="L4_X_4", instance_type="g6.12xlarge")
Machine.L4_X_8 = Machine(name="L4_X_8", instance_type="g6.48xlarge")
Machine.A10G = Machine(name="A10G", instance_type="g5.8xlarge")
Machine.A10G_X_4 = Machine(name="A10G_X_4", instance_type="g5.12xlarge")
Machine.A10G_X_8 = Machine(name="A10G_X_8", instance_type="g5.48xlarge")
Machine.L40S = Machine(name="L40S", instance_type="g6e.4xlarge")
Machine.L40S_X_4 = Machine(name="L40S_X_4", instance_type="g6e.12xlarge")
Machine.L40S_X_8 = Machine(name="L40S_X_8", instance_type="g6e.48xlarge")
Machine.A100_X_2 = Machine(name="A100_X_2", instance_type="a2-ultragpu-2g")  # GCP
Machine.A100_X_4 = Machine(name="A100_X_4", instance_type="a2-ultragpu-4g")  # GCP
Machine.A100_X_8 = Machine(name="A100_X_8", instance_type="p4d.24xlarge")
Machine.B200_X_8 = Machine(name="B200_X_8", instance_type="a4-highgpu-8g")  # GCP
Machine.H100_X_8 = Machine(name="H100_X_8", instance_type="p5.48xlarge")
Machine.H200_X_8 = Machine(name="H200_X_8", instance_type="p5en.48xlarge")
