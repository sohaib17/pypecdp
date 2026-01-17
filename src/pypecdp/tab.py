"""Tab/session management and DOM utilities."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any, Callable

from . import cdp
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
        self.doc: cdp.dom.Node | None = None
        self._handlers: dict[type[Any], list[Callable[[Any], Any]]] = {}
        self._frameid: cdp.page.FrameId | None = None

    async def send(
        self,
        cmd: Any,
        **kwargs: Any,
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
        return await self.browser.send(
            cmd,
            session_id=self.session_id,
            **kwargs,
        )

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
        if method in (cdp.dom.DocumentUpdated,):
            # Invalidate cached document on DOM changes
            self.doc = None
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
    ) -> cdp.target.SessionID:
        """Attach a CDP session to this tab.

        This method is used for manual tab attachment when auto_attach
        is disabled in the Browser configuration. If auto_attach is enabled
        (default), tabs are attached automatically by the Browser.

        Returns:
            SessionID: The session ID for this tab after attachment.
                If already attached, returns the existing session ID.

        Raises:
            RuntimeError: If the CDP attach_to_target command fails.
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
        self._frameid, *_ = await self.send(
            cdp.page.navigate(
                url=url,
            ),
        )
        if timeout > 0:
            await self.wait_for_event(
                event=cdp.page.LoadEventFired,
                timeout=timeout,
            )

    async def wait_for_event(
        self,
        event: type[Any] = cdp.page.LoadEventFired,
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

    async def find_elems(
        self,
        query: str,
        depth: int = 100,
        pierce: bool = True,
    ) -> list[Elem]:
        """Find all elements matching the specified query.

        Searches from the document root and includes iframes. To search
        within a specific element, use `Elem.query_selector()`.

        Args:
            query: Plain text, CSS selector, or XPath search query.
            depth: Max depth to retrieve the document node.
            pierce: Whether to pierce shadow DOM boundaries.

        Returns:
            list[Elem]: List of matching elements, empty if nothing found.
        """
        elems = []
        self.doc = await self.send(
            cdp.dom.get_document(
                depth,
                pierce,
            )
        )
        search_id, count = await self.send(
            cdp.dom.perform_search(
                query=query,
                include_user_agent_shadow_dom=True,
            )
        )
        if count:
            found_nodes: list[cdp.dom.NodeId] = await self.send(
                cdp.dom.get_search_results(
                    search_id=search_id,
                    from_index=0,
                    to_index=count,
                )
            )
            await self.send(
                cdp.dom.discard_search_results(
                    search_id,
                ),
            )
            for node_id in found_nodes:
                elems.append(self.elem(node_id))
        # Search in iframes
        frames = self._frame_nodes(self.doc)
        for frame in frames:
            frame_elems = await frame.find_elems(
                query=query,
                depth=depth,
                pierce=pierce,
            )
            elems.extend(frame_elems)
        return elems

    async def wait_for_elems(
        self,
        query: str,
        timeout: float = 10.0,
        **kwargs: Any,
    ) -> list[Elem]:
        """Wait for elements matching the specified query to appear.

        Args:
            query: Plain text, CSS selector, or XPath search query.
            timeout: Maximum seconds to wait.
            **kwargs: Additional arguments for `find_elems` method
                (e.g., depth, pierce, poll).

        Returns:
            list[Elem]: List of matching elements, empty if timeout.
        """
        poll: float = kwargs.get("poll", 0.5)
        depth: int = kwargs.get("depth", 100)
        pierce: bool = kwargs.get("pierce", True)
        end: float = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < end:
            elems: list[Elem] = await self.find_elems(query, depth, pierce)
            if elems:
                return elems
            await asyncio.sleep(poll)
        return []

    async def find_elem(
        self,
        query: str,
        depth: int = 100,
        pierce: bool = True,
    ) -> Elem | None:
        """Find the first element matching the specified query.

        Searches from the document root and includes iframes. To search
        within a specific element, use `Elem.query_selector()`.

        Args:
            query: Plain text, CSS selector, or XPath search query.
            depth: Max depth to retrieve the document node.
            pierce: Whether to pierce shadow DOM boundaries.

        Returns:
            Elem | None: The first matching element, or None if not found.
        """
        elems = await self.find_elems(query, depth, pierce)
        if elems:
            return elems[0]
        return None

    async def wait_for_elem(
        self,
        query: str,
        timeout: float = 10.0,
        **kwargs: Any,
    ) -> Elem | None:
        """Wait for an element matching the specified query to appear.

        Args:
            query: Plain text, CSS selector, or XPath search query.
            timeout: Maximum seconds to wait.
            **kwargs: Additional arguments for `find_elem` method
                (e.g., depth, pierce, poll).

        Returns:
            Elem | None: The matching element, or None if timeout.
        """
        elems = await self.wait_for_elems(query, timeout, **kwargs)
        if elems:
            return elems[0]
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
                cdp.target.close_target(
                    target_id=self.target_id,
                )
            )
        except (RuntimeError, ConnectionError):
            # Tab may already be closed or connection lost
            logger.debug("Could not close tab %s", self.target_id)

    # Attributes--------------------------------------------------------------

    @property
    def parent(
        self,
    ) -> Tab | None:
        """Get the parent tab if this tab is a child frame.

        This property is useful for navigating iframe hierarchies. Top-level
        tabs (pages) will have no parent, while iframes and nested frames
        will return their parent tab.

        Returns:
            Tab | None: The parent Tab instance if this is a frame/iframe,
                or None if this is a top-level page or parent not found.

        Example:
            >>> if tab.parent:
            ...     print(f"Frame in: {tab.parent.url}")
            ... else:
            ...     print("Top-level tab")
        """
        if self.target_info and self.target_info.parent_frame_id:
            return self.browser.targets.get(
                cdp.target.TargetID(self.target_info.parent_frame_id), None
            )
        return None

    def elem(
        self,
        node_id: cdp.dom.NodeId,
    ) -> Elem:
        """Create an Elem instance from a CDP NodeId.

        Searches the document tree for the node with the specified ID
        and wraps it in an Elem instance for interaction.

        Args:
            node_id: The NodeId of the DOM element to find.

        Returns:
            Elem: The created Elem instance wrapping the found node.

        Raises:
            ValueError: If the tab document is not loaded or if the node
                with the specified ID is not found.
        """

        def _filter(
            nid: cdp.dom.NodeId,
            root: cdp.dom.Node,
        ) -> Elem | None:
            if root.node_id == nid:
                return Elem(tab=self, node=root)
            node_children = root.children or []
            shadow_roots = root.shadow_roots or []
            children = node_children + shadow_roots
            for child in children:
                if child.node_id == nid:
                    return Elem(tab=self, node=child)
                if child.content_document:
                    elem = _filter(nid, child.content_document)
                else:
                    elem = _filter(nid, child)
                if elem:
                    return elem
            return None

        if self.doc is None:
            raise ValueError("Tab document not loaded")
        elem = _filter(node_id, self.doc)
        if elem:
            return elem
        raise ValueError(f"Node with id {node_id} not found in root")

    def _frame_nodes(
        self,
        node: cdp.dom.Node,
    ) -> list[Tab]:
        """Recursively find all iframe nodes and their corresponding Tab instances.

        Searches through the DOM tree for IFRAME elements and returns
        the associated Tab instances for each frame.

        Args:
            node: The DOM node to search within.

        Returns:
            list[Tab]: List of Tab instances for iframe elements found.
        """

        def _get_target(
            frame_id: cdp.page.FrameId,
        ) -> Tab | None:
            return next(
                (
                    self.browser.targets[t]
                    for t in self.browser.targets
                    if str(t) == str(frame_id)
                ),
                None,
            )

        out = []
        node_children = node.children or []
        shadow_roots = node.shadow_roots or []
        children = node_children + shadow_roots
        for child in children:
            if child.node_name == "IFRAME":
                if child.frame_id:
                    tab = _get_target(child.frame_id)
                    if tab:
                        out.append(tab)
                    else:
                        logger.debug(
                            "Could not find target for frame id %s",
                            child.frame_id,
                        )
            out.extend(self._frame_nodes(child))
        return out

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
