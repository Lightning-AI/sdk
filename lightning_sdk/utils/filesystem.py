from typing import Optional, TypedDict


class PathResult(TypedDict):
    owner: Optional[str]
    teamspace: Optional[str]
    studio: Optional[str]
    destination: Optional[str]


def parse_lit_url(url: str) -> PathResult:
    """Parse a ``lit://`` URL into its owner, teamspace, and destination components.

    Args:
        url: A URL in ``lit://owner/teamspace[/destination]`` format, or a bare
            ``owner/teamspace[/destination]`` path without the prefix.

    Returns:
        PathResult: A dict with ``owner``, ``teamspace``, ``studio``, and ``destination``
        keys.  ``studio`` is always ``None`` (reserved for future use).

    Raises:
        ValueError: If the path is empty after stripping the prefix, or if fewer than
            two path components are present.
    """
    prefix = "lit://"
    path_string = url[len(prefix) :] if url.startswith(prefix) else url
    if not path_string:
        raise ValueError("Teamspace path cannot be empty after prefix")

    result: PathResult = {"owner": None, "teamspace": None, "studio": None, "destination": None}

    path_parts = path_string.split("/")
    if len(path_parts) < 2:
        raise ValueError("Invalid lit URL format. Expected at least 'lit://<owner>/<teamspace>'")

    # get teamspace
    result["owner"], result["teamspace"] = path_parts[0], path_parts[1]

    # path
    result["destination"] = "/".join(path_parts[2:]) if len(path_parts) > 2 else ""

    return result
