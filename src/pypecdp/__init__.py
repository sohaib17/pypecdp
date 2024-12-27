"""Public API for pypecdp.

Exports:
    Browser, Tab, Elem, Config
"""

from __future__ import annotations

import logging

logger = logging.getLogger("pypecdp")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

from .browser import Browser
from .config import Config
from .elem import Elem
from .tab import Tab

__all__ = ["Browser", "Tab", "Elem", "Config"]
__version__ = "0.1.7"
