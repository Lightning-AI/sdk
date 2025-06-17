class Schedule:
    def __init__(self, name: str, cron_expression: str) -> None:
        self.name = name
        self.cron_expression = cron_expression
