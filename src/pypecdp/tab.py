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
        target_id: cdp.target.TargetID,
        target_info: cdp.target.TargetInfo | None = None,
    ) -> None:
        """Initialize a Tab instance.

        Args:
            browser: The Browser instance managing this tab.
            target_id: CDP target identifier.
            target_info: Optional target metadata.
        """
        self.browser: Browser = browser
        self.target_id: cdp.target.TargetID = target_id
        self.target_info: cdp.target.TargetInfo | None = target_info
        self.session_id: cdp.target.SessionID | None = None
        self._handlers: dict[type[Any], list[Callable[[Any], Any]]] = {}
        self._frameid: cdp.page.FrameId | None = None

    async def init(
        self,
        cmd_array: list[Any] | None = None,
    ) -> None:
        """Initialize CDP domains for this tab.

        Enables Page and DOM domains by default.

        Args:
            cmd_array: Optional list of CDP command generators to send
                for initialization. If None, defaults to enabling
                Page and DOM domains.
        """
        if cmd_array is None:
            cmd_array = [
                cdp.page.enable(),
                cdp.dom.enable(),
            ]
        for cmd in cmd_array:
            await self.send(cmd)

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

    def clear_handlers(
        self,
    ) -> None:
        """Clear all registered event handlers for this tab."""
        self._handlers.clear()

    async def attach(
        self,
    ) -> cdp.target.SessionID | None:
        """Attach a CDP session to this tab.

        Returns:
            SessionID | None: The session ID for this tab, or None if already attached.

        Raises:
            RuntimeError: If attaching to the target fails.
        """
        if not self.session_id:
            # Attach to target and get session ID
            self.session_id = await self.browser.send(
                cdp.target.attach_to_target(
                    target_id=self.target_id,
                    flatten=True,
                )
            )
        return self.session_id

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
        self._frameid, *_ = await self.send(cdp.page.navigate(url=url))
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
            logger.debug("Event %s fired for tab %s", event.__name__, self)
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
    ) -> cdp.runtime.RemoteObject:
        """Evaluate JavaScript expression in the page context.

        Args:
            expression: JavaScript code to evaluate.
            await_promise: Whether to await if expression returns a Promise.

        Returns:
            RemoteObject: The result of the evaluation.
        """
        result: cdp.runtime.RemoteObject
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
        depth: int = 1,
        pierce: bool = False,
    ) -> Elem | None:
        """Find the first element matching a CSS selector.

        Args:
            selector: CSS selector string.
            depth: Depth to retrieve the document node.
            pierce: Whether to pierce shadow DOM boundaries.

        Returns:
            Elem | None: The matching element, or None if not found.
        """
        root = await self.send(cdp.dom.get_document(depth, pierce))
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
        depth: int = 1,
        pierce: bool = False,
    ) -> list[Elem]:
        """Find all elements matching a CSS selector.

        Args:
            selector: CSS selector string.
            depth: Depth to retrieve the document node.
            pierce: Whether to pierce shadow DOM boundaries.

        Returns:
            list[Elem]: List of matching elements (may be empty).
        """
        root = await self.send(cdp.dom.get_document(depth, pierce))
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
        **kwargs: Any,
    ) -> Elem | None:
        """Wait for an element matching a selector to appear.

        Args:
            selector: CSS selector string.
            timeout: Maximum seconds to wait.
            poll: Polling interval in seconds.
            **kwargs: Additional arguments for `select` method
                (e.g., depth, pierce).

        Returns:
            Elem | None: The matching element, or None if timeout.
        """
        depth: int = kwargs.get("depth", 1)
        pierce: bool = kwargs.get("pierce", False)
        end: float = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < end:
            el: Elem | None = await self.select(selector, depth, pierce)
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

    # Attributes--------------------------------------------------------------

    def __repr__(
        self,
    ) -> str:
        """Get a string representation of the Tab.

        Returns:
            str: String representation of the Tab.
        """
        attrs = []
        attrs.append(f"id={self.target_id}")
        if self.session_id:
            attrs.append(f"session={self.session_id}")
        if self.target_info:
            attrs.append(f"type={self.target_info.type_}")
            if self.target_info.title:
                attrs.append(f'title="{self.target_info.title}"')
        return f"<Tab {' '.join(attrs)}>"

    def __getattr__(
        self,
        name: str,
    ) -> Any:
        """Delegate attribute access to target_info if available.

        Args:
            name: The attribute name to access.
        Returns:
            Any: The attribute value from target_info.
        Raises:
            AttributeError: If the attribute is not found.
        """
        if name == "type":
            name = "type_"
        if self.target_info and hasattr(self.target_info, name):
            return getattr(self.target_info, name)
        raise AttributeError(f"'Tab' object has no attribute '{name}'")


__all__ = ["Tab"]
