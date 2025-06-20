from dataclasses import dataclass
from typing import Optional


@dataclass
class Schedule:
    cron_expression: str
    name: Optional[str] = None
