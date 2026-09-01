"""Fault tolerance strategy for multi-machine jobs.

This is a leaf module (it only depends on the generated OpenAPI models) so it
can be imported freely by both :mod:`lightning_sdk.mmt` and
:mod:`lightning_sdk.api.mmt_api` without introducing import cycles.
"""

from enum import Enum
from typing import Optional

from lightning_sdk.lightning_cloud.openapi.models import (
    V1MultiMachineJobFaultTolerance,
    V1MultiMachineJobFaultToleranceStrategy,
)

__all__ = ["MMTFaultToleranceStrategy", "_to_fault_tolerance"]


class MMTFaultToleranceStrategy(str, Enum):
    """Fault tolerance strategy for multi-machine jobs.

    Only ``RECREATE_ALL_NODES`` is currently supported beyond the default
    (``UNSPECIFIED``). The strategy is set at the multi-machine job level, not
    on the per-machine ``JobSpec``.
    """

    UNSPECIFIED = V1MultiMachineJobFaultToleranceStrategy.UNSPECIFIED
    RECREATE_ALL_NODES = V1MultiMachineJobFaultToleranceStrategy.RECREATE_ALL_NODES


def _to_fault_tolerance(
    strategy: Optional[MMTFaultToleranceStrategy],
) -> Optional[V1MultiMachineJobFaultTolerance]:
    """Map a public :class:`MMTFaultToleranceStrategy` to the generated API model.

    Returns ``None`` for ``None`` / :attr:`MMTFaultToleranceStrategy.UNSPECIFIED`
    (the backend treats an unset strategy as ``UNSPECIFIED``). Raises
    :class:`ValueError` for any unsupported strategy value.
    """
    if strategy == MMTFaultToleranceStrategy.RECREATE_ALL_NODES:
        return V1MultiMachineJobFaultTolerance(
            strategy=V1MultiMachineJobFaultToleranceStrategy.RECREATE_ALL_NODES
        )
    return V1MultiMachineJobFaultTolerance(
        strategy=V1MultiMachineJobFaultToleranceStrategy.UNSPECIFIED
    )
