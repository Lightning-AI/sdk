from typing import Optional, TypedDict


class PathResult(TypedDict):
    owner: Optional[str]
    teamspace: Optional[str]
    studio: Optional[str]
    destination: Optional[str]


_SHORT_FORM_ERROR = (
    "Invalid lit URL {url!r}. Expected 'lit://<owner>/<teamspace>[/<path>]', or 'lit:///<path>' "
    "for a path in the current teamspace."
)


def parse_lit_url(url: str) -> PathResult:
    """Parse a ``lit://`` URL into its owner, teamspace, and destination components.

    Two forms are supported:

    - Long form: ``lit://<owner>/<teamspace>[/<destination>]``.
    - Relative form: ``lit:///<destination>`` — a path in the current teamspace.
      ``owner`` and ``teamspace`` are returned as ``None`` and resolve to the
      configured defaults (or the Studio's teamspace when running in one).

    A bare ``owner/teamspace[/destination]`` path without the prefix is also accepted;
    a bare absolute path (e.g. ``/tmp/file``) is rejected, since only the ``lit:///``
    spelling means "the current teamspace" — never a stray local path.

    Returns:
        PathResult: A dict with ``owner``, ``teamspace``, ``studio``, and ``destination``
        keys.  ``studio`` is always ``None`` (reserved for future use).

    Raises:
        ValueError: If the path is empty after stripping the prefix, or if it is neither
            a relative form nor has the owner and teamspace components.
    """
    prefix = "lit://"
    has_prefix = url.startswith(prefix)
    path_string = url[len(prefix) :] if has_prefix else url
    if not path_string:
        raise ValueError("Teamspace path cannot be empty after prefix")

    result: PathResult = {"owner": None, "teamspace": None, "studio": None, "destination": None}

    if path_string.startswith("/"):
        # Relative form: lit:///<destination> targets the current teamspace.
        # An empty destination is the teamspace root, as in the long form.
        # A bare absolute path is a local-path mistake, not a drive path — callers
        # like Filesystem.rm would otherwise turn it into a remote operation.
        destination = path_string[1:]
        if not has_prefix or destination.startswith("/"):
            raise ValueError(_SHORT_FORM_ERROR.format(url=url))
        result["destination"] = destination
        return result

    path_parts = path_string.split("/")
    if len(path_parts) < 2:
        raise ValueError(_SHORT_FORM_ERROR.format(url=url))

    # get teamspace
    result["owner"], result["teamspace"] = path_parts[0], path_parts[1]

    # path
    result["destination"] = "/".join(path_parts[2:]) if len(path_parts) > 2 else ""

    return result
