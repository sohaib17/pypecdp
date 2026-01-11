"""Centralized logging configuration for pypecdp.

The logger can be configured via environment variables:
    PYPECDP_LOGGER: Logger name (default: "pypecdp")
    PYPECDP_LOGLEVEL: Log level (default: "INFO")

Example:
    export PYPECDP_LOGGER=myapp.browser
    export PYPECDP_LOGLEVEL=DEBUG
"""

from __future__ import annotations

import logging
import os


def get_logger() -> logging.Logger:
    """Get the pypecdp logger instance.

    Configurable via environment variables:
        PYPECDP_LOGGER: Logger name (default: "pypecdp")
        PYPECDP_LOGLEVEL: Log level (default: "INFO")

    Returns:
        logging.Logger: The shared logger for pypecdp.
    """
    name = os.environ.get("PYPECDP_LOGGER", "pypecdp")
    level = os.environ.get("PYPECDP_LOGLEVEL", "INFO").upper()
    new_logger = logging.getLogger(name)
    fmt = "%(asctime)s [%(process)d][%(levelname)s] %(message)s"
    formatter = logging.Formatter(fmt, "%b %d %I:%M:%S")
    new_logger.setLevel(level)
    # Remove any existing handlers to avoid duplicates
    for handler in new_logger.handlers:
        new_logger.removeHandler(handler)
    # Add default StreamHandler for console output
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(formatter)
    new_logger.addHandler(handler)
    return new_logger


# Single shared logger instance for the entire package
logger: logging.Logger = get_logger()

__all__ = ["logger", "get_logger"]
