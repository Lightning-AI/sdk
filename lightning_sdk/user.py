from typing import Optional


class User:
    """Represents a user owner of teamspaces and studios.

    Args:
        name: the name of the user

    Note:
        Arguments will be automatically inferred from environment variables if possible,
        unless explicitly specified

    """

    def __init__(self, name: Optional[str] = None) -> None:
        super().__init__()
