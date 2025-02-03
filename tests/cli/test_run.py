from typing import Dict

import pytest

from lightning_sdk.cli.run import _Run


@pytest.mark.parametrize(
    ("input_mappings", "expected"),
    [
        ("", {}),
        ("container_path1:connection_1:path1", {"container_path1": "connection_1:path1"}),
        (
            "container_path1:connection_1,/container_path_2:connection-2:path2, /container-path3:connection-3",
            {
                "container_path1": "connection_1",
                "/container_path_2": "connection-2:path2",
                "/container-path3": "connection-3",
            },
        ),
    ],
)
def test_parse_run_path_mapping(input_mappings: str, expected: Dict[str, str]):
    assert _Run._resolve_path_mapping(input_mappings) == expected
