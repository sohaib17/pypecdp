"""Module for utility functions used in PypeCDP."""

from __future__ import annotations

import asyncio
import functools
from http import cookiejar
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

from . import cdp

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


class CookieJar(cookiejar.CookieJar):
    """Custom CookieJar for pypecdp.

    Inherits from http.cookiejar.CookieJar to manage cookies
    within the pypecdp browser context. Properly converts CDP cookies
    to standard Python cookiejar.Cookie objects.

    The original CDP cookies are preserved in the ``cdp_cookies`` attribute,
    allowing access to CDP-specific properties (priority, source_scheme,
    source_port, same_site, partition_key, etc.) that aren't available
    in standard cookiejar.Cookie objects.

    Attributes:
        cdp_cookies: List of original cdp.network.Cookie objects used to
            populate this CookieJar. None if the jar was created empty.

    Args:
        cdp_cookies: Optional list of CDP cookies to populate the jar.
    """

    def __init__(
        self,
        cdp_cookies: list[cdp.network.Cookie] | None = None,
    ) -> None:
        """Initialize the CookieJar with optional CDP cookies.

        Args:
            cdp_cookies: List of CDP network.Cookie objects to convert.
        """
        super().__init__()
        # Store original CDP cookies for reference
        self.cdp_cookies = cdp_cookies
        # Convert and add CDP cookies to the CookieJar
        if cdp_cookies:
            for cdp_cookie in cdp_cookies:
                # Determine domain matching behavior
                domain = cdp_cookie.domain
                domain_initial_dot = domain.startswith(".")
                # Handle expiry: CDP uses -1 for session, None for unrepresentable
                # CookieJar expects None for session, timestamp for persistent
                expires = None
                discard = cdp_cookie.session
                if (
                    not cdp_cookie.session
                    and cdp_cookie.expires is not None
                    and cdp_cookie.expires >= 0
                ):
                    expires = int(cdp_cookie.expires)
                cookie = cookiejar.Cookie(
                    version=0,  # Netscape cookies (standard)
                    name=cdp_cookie.name,
                    value=cdp_cookie.value,
                    port=None,
                    port_specified=False,
                    domain=domain,
                    domain_specified=True,
                    domain_initial_dot=domain_initial_dot,
                    path=cdp_cookie.path,
                    path_specified=True,
                    secure=cdp_cookie.secure,
                    expires=expires,
                    discard=discard,
                    comment=None,
                    comment_url=None,
                    rest={"HttpOnly": str(cdp_cookie.http_only)},
                    rfc2109=False,
                )
                self.set_cookie(cookie)


__all__ = ["tab_attached", "CookieJar"]
