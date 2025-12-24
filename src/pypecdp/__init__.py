"""Public API for pypecdp.

Exports:
    Browser, Tab, Elem, Config, cdp, logger
"""

from __future__ import annotations

import importlib.metadata

from . import cdp
from .browser import Browser
from .config import Config
from .elem import Elem
from .logger import logger
from .tab import Tab

__all__: list[str] = [
    "Browser",
    "Tab",
    "Elem",
    "Config",
    "cdp",
    "logger",
]
__version__: str = importlib.metadata.version("pypecdp")
