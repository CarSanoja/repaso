import logging
import sys

TELEMETRY_LOGGER = "repaso.telemetry"
HANDLER_NAME = "repaso-telemetry-stream"
LINE_FORMAT = "%(message)s"


def _stream_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.name = HANDLER_NAME
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(LINE_FORMAT))
    return handler


def telemetry_logger() -> logging.Logger:
    logger = logging.getLogger(TELEMETRY_LOGGER)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(handler.name == HANDLER_NAME for handler in logger.handlers):
        logger.addHandler(_stream_handler())
    return logger
