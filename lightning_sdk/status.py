from enum import Enum


class Status(Enum):
    NotCreated = 1
    Pending = 2
    Running = 3
    Stopping = 4
    Stopped = 5
    Failed = 6
