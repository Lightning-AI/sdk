from enum import Enum


class Machine(Enum):
    """Enum holding all supported machine types for studios."""

    CPU = "CPU"
    DATA_PREP = "DATA_PREP"
    T4 = "T4"
    T4_X_4 = "T4_X_4"
    V100 = "V100"
    V100_X_4 = "V100_X_4"
    A10G = "A10G"
    A10G_X_4 = "A10G_X_4"
    A100_X_8 = "A100_X_8"
