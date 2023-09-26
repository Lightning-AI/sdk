from enum import Enum


class Status(Enum):
    """Enum holding all possible studio status types."""

    NotCreated = 1
    Pending = 2
    Running = 3
    Stopping = 4
    Stopped = 5
    Failed = 6
