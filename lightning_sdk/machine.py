from lightning_sdk.utils.enum import DeprecationEnum


class Machine(DeprecationEnum):
    """Enum holding all supported machine types for studios."""

    CPU_SMALL = "CPU_SMALL"
    CPU = "CPU"
    DATA_PREP = "DATA_PREP"
    DATA_PREP_MAX = "DATA_PREP_MAX"
    DATA_PREP_ULTRA = "DATA_PREP_ULTRA"
    T4 = "T4"
    T4_X_4 = "T4_X_4"
    L4 = "L4"
    L4_X_4 = "L4_X_4"
    L4_X_8 = "L4_X_8"
    A10G = "A10G"
    A10G_X_4 = "A10G_X_4"
    A10G_X_8 = "A10G_X_8"
    L40S = "L40S"
    L40 = "L40", "L40S"  # deprecated
    L40S_X_4 = "L40S_X_4"
    L40_X_4 = "L40_X_4", "L40S_X_4"  # deprecated
    L40S_X_8 = "L40S_X_8"
    L40_X_8 = "L40_X_8", "L40S_X_8"  # deprecated
    A100_X_8 = "A100_X_8"
    H100_X_8 = "H100_X_8"
    H200_X_8 = "H200_X_8"
