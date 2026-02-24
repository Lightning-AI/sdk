from typing import Optional, TypedDict


class PathResult(TypedDict):
    owner: Optional[str]
    teamspace: Optional[str]
    studio: Optional[str]
    destination: Optional[str]


def parse_lit_url(url: str) -> PathResult:
    path_string = url.removeprefix("lit://")
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
