"""Public API for pypecdp.

Exports:
    Browser, Tab, Elem, Config, cdp
"""

from __future__ import annotations

import importlib.metadata
import logging

logger = logging.getLogger("pypecdp")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

from . import cdp
from .browser import Browser
from .config import Config
from .elem import Elem
from .tab import Tab

__all__ = ["Browser", "Tab", "Elem", "Config", "cdp"]
__version__ = importlib.metadata.version(__name__)
