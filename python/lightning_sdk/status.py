from enum import Enum


class Status(Enum):
    """Enum holding all possible studio status types."""

    NotCreated = "NotCreated"
    Pending = "Pending"
    Running = "Running"
    Stopping = "Stopping"
    Stopped = "Stopped"
    Completed = "Completed"
    Failed = "Failed"

    def __str__(self) -> str:
        """String representation of the enum."""
        return self.value
