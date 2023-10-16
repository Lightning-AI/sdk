import logging


def _setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    _logger = logging.getLogger(name)
    _handler = logging.StreamHandler()
    _handler.setLevel(level)
    _logger.setLevel(level)
    _formatter = logging.Formatter("%(levelname)s - %(message)s")
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
    return _logger
