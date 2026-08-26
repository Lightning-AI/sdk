"""Path parsing and resolution for the deprecated ``lightning studio cp/ls/rm`` commands.

The main drive commands (``lightning cp/ls/rm``) go through
:func:`lightning_sdk.utils.filesystem.parse_lit_url` instead; the parser here
additionally accepts the studio commands' legacy short forms.
"""

from typing import Optional

from lightning_sdk.cli.utils.resource_resolution import join_teamspace_slug
from lightning_sdk.cli.utils.resource_resolution import resolve_studio as resolve_cli_studio
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace as resolve_cli_teamspace
from lightning_sdk.studio import Studio
from lightning_sdk.utils.filesystem import PathResult


def parse_studio_path(studio_path: str) -> PathResult:
    """Parse a studio ``lit://`` URL into owner, teamspace, studio, and destination.

    Accepts ``lit://[owner/][teamspace/]studios/<studio>/<path>``, the short form
    ``lit://<studio>/<path>``, and the relative form ``lit:///studios/<studio>/<path>``
    (a studio in the current teamspace). Omitted owner and teamspace resolve to the
    configured defaults.
    """
    prefix = "lit://"
    has_prefix = studio_path.startswith(prefix)
    path_string = studio_path[len(prefix) :] if has_prefix else studio_path
    if not path_string:
        raise ValueError("Studio path cannot be empty after prefix")

    result: PathResult = {"owner": None, "teamspace": None, "studio": None, "destination": None}

    relative = path_string.startswith("/")
    if relative:
        # Relative form: lit:///... targets the current teamspace, which is also
        # what the short forms below resolve to when owner/teamspace are omitted.
        # Only the lit:/// spelling means that — a bare absolute path is a
        # local-path mistake, not a studio path.
        path_string = path_string[1:]
        if not has_prefix or path_string.startswith("/") or (path_string and not path_string.startswith("studios/")):
            raise ValueError(
                f"Invalid studio path {studio_path!r}. Expected 'lit://<owner>/<teamspace>/studios/<studio>/<path>' "
                "or 'lit:///studios/<studio>/<path>' for the current teamspace."
            )
        if not path_string:
            raise ValueError("Studio path cannot be empty after prefix")

    if relative:
        # lit:///studios/<studio>/<path> — the leading root has no owner/teamspace
        # before it, so the "/studios/" split below would not match it.
        path_parts = path_string[len("studios/") :].split("/")

    elif "/studios/" in path_string:
        prefix_part, suffix_part = path_string.split("/studios/", 1)

        # org and teamspace
        if prefix_part:
            org_ts_components = prefix_part.split("/")
            if len(org_ts_components) == 2:
                result["owner"], result["teamspace"] = org_ts_components
            elif len(org_ts_components) == 1:
                result["teamspace"] = org_ts_components[0]
            else:
                raise ValueError(f"Invalid format: '{prefix_part}'")

        # studio and destination
        path_parts = suffix_part.split("/")

    else:
        # studio and destination
        path_parts = path_string.split("/")

    if not path_parts or not path_parts[0]:
        raise ValueError("Invalid: Missing studio name.")

    if len(path_parts) == 1:
        raise ValueError(
            "Invalid: Invalid studio path. To refer to the studio root, add a trailing '/' (e.g., 'lit://<owner>/<my-teamspace>/studios/<my-studio>/')"
        )

    result["studio"] = path_parts[0]
    result["destination"] = "/".join(path_parts[1:])

    return result


def resolve_studio(studio_name: Optional[str], teamspace: Optional[str], owner: Optional[str]) -> Studio:
    resolved_teamspace = resolve_cli_teamspace(join_teamspace_slug(owner, teamspace))
    return resolve_cli_studio(studio_name, resolved_teamspace)
