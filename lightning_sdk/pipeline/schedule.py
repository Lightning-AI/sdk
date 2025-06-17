from dataclasses import dataclass


@dataclass
class Schedule:
    name: str
    cron_expression: str
