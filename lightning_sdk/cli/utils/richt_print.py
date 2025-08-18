import os
from typing import Any

from rich.console import Console


def rich_to_str(*renderables: Any) -> str:
    with open(os.devnull, "w") as f:
        console = Console(file=f, record=True)
        console.print(*renderables)
    return console.export_text(styles=True)
