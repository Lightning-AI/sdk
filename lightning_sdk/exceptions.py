class OutOfCapacityError(RuntimeError):
    """Raised when the requested machine is not available in the selected cloud account."""


class NotSupportedError(RuntimeError):
    """Raised when the requested machine is not supported in the selected cloud account."""
