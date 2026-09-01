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

__all__ = ["MMTFaultToleranceStrategy", "_to_fault_tolerance", "_from_fault_tolerance"]


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

    Always returns a :class:`V1MultiMachineJobFaultTolerance`. ``None`` and
    :attr:`MMTFaultToleranceStrategy.UNSPECIFIED` (and any unsupported value)
    map to the ``UNSPECIFIED`` strategy, which the backend treats as "no fault
    tolerance". Only :attr:`MMTFaultToleranceStrategy.RECREATE_ALL_NODES` is
    currently supported beyond the default.
    """
    if strategy == MMTFaultToleranceStrategy.RECREATE_ALL_NODES:
        return V1MultiMachineJobFaultTolerance(strategy=V1MultiMachineJobFaultToleranceStrategy.RECREATE_ALL_NODES)
    return V1MultiMachineJobFaultTolerance(strategy=V1MultiMachineJobFaultToleranceStrategy.UNSPECIFIED)


def _from_fault_tolerance(
    fault_tolerance: Optional[V1MultiMachineJobFaultTolerance],
) -> Optional[MMTFaultToleranceStrategy]:
    """Map a generated fault tolerance model back to the public enum.

    Returns ``None`` when ``fault_tolerance`` is ``None`` (e.g. a job whose
    payload predates the field). Otherwise maps the stored strategy to the
    public :class:`MMTFaultToleranceStrategy`; any value other than
    :attr:`MMTFaultToleranceStrategy.RECREATE_ALL_NODES` (including
    ``UNSPECIFIED`` and unknown backend values) is reported as
    :attr:`MMTFaultToleranceStrategy.UNSPECIFIED`.
    """
    if fault_tolerance is None:
        return None
    strategy = getattr(fault_tolerance, "strategy", None)
    if strategy == V1MultiMachineJobFaultToleranceStrategy.RECREATE_ALL_NODES:
        return MMTFaultToleranceStrategy.RECREATE_ALL_NODES
    return MMTFaultToleranceStrategy.UNSPECIFIED
