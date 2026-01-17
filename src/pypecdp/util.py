"""Module for utility functions used in PypeCDP."""

from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

if TYPE_CHECKING:
    from .elem import Elem

F = TypeVar("F", bound=Callable[..., Any])


def tab_attached(func: F) -> F:
    """Decorator to ensure the element's tab session is still active.

    Checks if elem.tab.session_id is None before executing the method.
    Also catches RuntimeError with "Session with given id not found" and
    re-raises as ReferenceError for consistent error handling.

    Args:
        func: The Elem method to wrap.

    Returns:
        The wrapped method.

    Raises:
        ReferenceError: If elem.tab.session_id is None or if the session
            is no longer found by the browser.

    Example:
        @tab_attached
        async def click(self) -> None:
            # Method implementation
            ...
    """

    @functools.wraps(func)
    async def wrapper(self: Elem, *args: Any, **kwargs: Any) -> Any:
        msg = f"Target {self.tab.target_id} is no longer available."
        if self.tab.session_id is None:
            raise ReferenceError(msg)
        try:
            result = await func(self, *args, **kwargs)
            await asyncio.sleep(0)
            return result
        except RuntimeError as e:
            if "Session with given id not found" in str(e):
                raise ReferenceError(msg) from e
            raise

    return cast(F, wrapper)


__all__ = ["tab_attached"]
