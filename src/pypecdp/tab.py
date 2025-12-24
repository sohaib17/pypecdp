"""Tab/session management and DOM utilities."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any, Callable

from . import cdp
from .cdp.page import LoadEventFired
from .elem import Elem
from .logger import logger

if TYPE_CHECKING:
    from .browser import Browser


class Tab:
    """Represents a browser tab/target with CDP session.

    Manages a CDP session for a specific target, handles event
    dispatching, and provides methods for navigation and DOM queries.

    Attributes:
        browser: The parent Browser instance.
        target_id: CDP target identifier.
        target_info: Optional target metadata.
        session_id: CDP session ID for this tab.
    """

    def __init__(
        self,
        browser: Browser,
        target_id: Any,
        target_info: Any = None,
    ) -> None:
        """Initialize a Tab instance.

        Args:
            browser: The Browser instance managing this tab.
            target_id: CDP target identifier.
            target_info: Optional target metadata.
        """
        self.browser: Browser = browser
        self.target_id: Any = target_id
        self.target_info: Any = target_info
        self.session_id: str | None = None
        self._handlers: dict[type[Any], list[Callable[[Any], Any]]] = {}

    async def init(
        self,
    ) -> None:
        """Initialize CDP domains for this tab.

        Enables Page, Runtime, DOM, and Log domains.
        """
        await self.send(cdp.page.enable())
        await self.send(cdp.runtime.enable())
        await self.send(cdp.dom.enable())
        await self.send(cdp.log.enable())

    async def send(
        self,
        cmd: Any,
    ) -> Any:
        """Send a CDP command within this tab's session.

        Args:
            cmd: CDP command generator to send.

        Returns:
            The parsed response from the CDP command.

        Raises:
            RuntimeError: If the tab is not attached or command fails.
        """
        if not self.session_id:
            raise RuntimeError(f"Tab {self.target_id} not attached")
        return await self.browser.send(cmd, session_id=self.session_id)

    def on(
        self,
        event_name: type[Any],
        handler: Callable[[Any], Any],
    ) -> None:
        """Register an event handler for tab-level CDP events.

        Args:
            event_name: The CDP event type to listen for.
            handler: Callback function or coroutine to handle events.
        """
        self._handlers.setdefault(event_name, []).append(handler)

    async def handle_event(
        self,
        event: Any,
    ) -> None:
        """Dispatch a CDP event to registered handlers.

        Args:
            event: The CDP event object to dispatch.
        """
        method: type[Any] = type(event)
        for h in self._handlers.get(method, []):
            try:
                if asyncio.iscoroutinefunction(h) or asyncio.iscoroutine(h):
                    await h(event)
                else:
                    h(event)
            except Exception:
                logger.exception("Tab handler error for %s", method)

    def clear_handlers(self) -> None:
        """Clear all registered event handlers for this tab."""
        self._handlers.clear()

    # Navigation & evaluation ------------------------------------------------

    async def navigate(
        self,
        url: str,
        timeout: float = 10.0,
    ) -> None:
        """Navigate to a URL and wait for page load.

        Args:
            url: The URL to navigate to.
            timeout: Maximum seconds to wait for load event. Set to 0
                to skip waiting.
        """
        await self.send(cdp.page.navigate(url=url))
        if timeout > 0:
            await self.wait_for_event(event=LoadEventFired, timeout=timeout)

    async def wait_for_event(
        self,
        event: type[Any] = LoadEventFired,
        timeout: float = 10.0,
    ) -> None:
        """Wait for a specific CDP event to occur.

        Args:
            event: The CDP event type to wait for.
            timeout: Maximum seconds to wait. Timeout errors are
                suppressed.
        """
        fut: asyncio.Future[None] = asyncio.get_running_loop().create_future()

        async def on_loaded(_: Any) -> None:
            if not fut.done():
                fut.set_result(None)
            # remove once fired
            handlers: list[Callable[[Any], Any]] = self._handlers.get(
                event, []
            )
            if on_loaded in handlers:
                handlers.remove(on_loaded)

        self.on(event, on_loaded)
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(fut, timeout=timeout)

    async def eval(
        self,
        expression: str,
        await_promise: bool = True,
    ) -> Any:
        """Evaluate JavaScript expression in the page context.

        Args:
            expression: JavaScript code to evaluate.
            await_promise: Whether to await if expression returns a Promise.

        Returns:
            The result of the evaluation (RemoteObject or primitive value).
        """
        result, _ = await self.send(
            cdp.runtime.evaluate(
                expression=expression,
                await_promise=await_promise,
            )
        )
        return result

    # DOM selection ----------------------------------------------------------

    async def select(
        self,
        selector: str,
    ) -> Elem | None:
        """Find the first element matching a CSS selector.

        Args:
            selector: CSS selector string.

        Returns:
            Elem | None: The matching element, or None if not found.
        """
        root = await self.send(cdp.dom.get_document())
        node_id = root.node_id
        result_node_id = await self.send(
            cdp.dom.query_selector(node_id=node_id, selector=selector)
        )
        # NodeId(0) means no match found
        return (
            Elem(self, result_node_id)
            if result_node_id and int(result_node_id) != 0
            else None
        )

    async def select_all(
        self,
        selector: str,
    ) -> list[Elem]:
        """Find all elements matching a CSS selector.

        Args:
            selector: CSS selector string.

        Returns:
            list[Elem]: List of matching elements (may be empty).
        """
        root = await self.send(cdp.dom.get_document())
        node_id = root.node_id
        node_ids = await self.send(
            cdp.dom.query_selector_all(node_id=node_id, selector=selector)
        )
        return [Elem(self, nid) for nid in node_ids]

    async def wait_for_selector(
        self,
        selector: str,
        timeout: float = 10.0,
        poll: float = 0.05,
    ) -> Elem | None:
        """Wait for an element matching a selector to appear.

        Args:
            selector: CSS selector string.
            timeout: Maximum seconds to wait.
            poll: Polling interval in seconds.

        Returns:
            Elem | None: The matching element, or None if timeout.
        """
        end: float = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < end:
            el: Elem | None = await self.select(selector)
            if el:
                return el
            await asyncio.sleep(poll)
        return None

    async def close(
        self,
    ) -> None:
        """Close this tab.

        Sends a close target command. Errors are suppressed if the tab
        is already closed or connection is lost.
        """
        try:
            await self.browser.send(
                cdp.target.close_target(target_id=self.target_id)
            )
        except (RuntimeError, ConnectionError):
            # Tab may already be closed or connection lost
            logger.debug("Could not close tab %s", self.target_id)
