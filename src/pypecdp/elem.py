"""DOM element wrapper and interactions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import cdp
from .logger import logger
from .util import tab_attached

if TYPE_CHECKING:
    from .tab import Tab


@dataclass
class Position:
    """Container for element coordinates.

    Quad format from CDP is [x1, y1, x2, y2, x3, y3, x4, y4]
    where points are ordered: top-left, top-right, bottom-right, bottom-left
    """

    quad: cdp.dom.Quad

    @property
    def top_left(self) -> tuple[float, float]:
        """Top-left corner coordinates (x, y)."""
        return (self.quad[0], self.quad[1])

    @property
    def top_right(self) -> tuple[float, float]:
        """Top-right corner coordinates (x, y)."""
        return (self.quad[2], self.quad[3])

    @property
    def bottom_right(self) -> tuple[float, float]:
        """Bottom-right corner coordinates (x, y)."""
        return (self.quad[4], self.quad[5])

    @property
    def bottom_left(self) -> tuple[float, float]:
        """Bottom-left corner coordinates (x, y)."""
        return (self.quad[6], self.quad[7])

    @property
    def center(self) -> tuple[float, float]:
        """Center point coordinates (x, y)."""
        xs = [self.quad[0], self.quad[2], self.quad[4], self.quad[6]]
        ys = [self.quad[1], self.quad[3], self.quad[5], self.quad[7]]
        return (sum(xs) / 4.0, sum(ys) / 4.0)

    @property
    def width(self) -> float:
        """Width of the element."""
        return float(abs(self.quad[2] - self.quad[0]))

    @property
    def height(self) -> float:
        """Height of the element."""
        return float(abs(self.quad[5] - self.quad[1]))

    def __repr__(self) -> str:
        """String representation of Position."""
        return f"Position(center={self.center}, width={self.width:.1f}, height={self.height:.1f})"


@dataclass
class Elem:
    """Wrapper for DOM elements with interaction methods.

    Provides high-level methods for interacting with elements in the
    browser, including clicking, typing, and retrieving attributes.

    Attributes:
        tab: The Tab instance containing this element.
        node: The CDP Node object representing the DOM element.

    Note:
        Additional node properties like node_id and backend_node_id
        are accessible via __getattr__ delegation to the node object.
    """

    tab: Tab
    node: cdp.dom.Node

    @tab_attached
    async def scroll_into_view(
        self,
    ) -> None:
        """Scroll element into viewport and attempt to focus it.

        Errors are suppressed if the element is detached or hidden.

        Raises:
            ReferenceError: If the tab session is no longer active.
        """
        if not self.backend_node_id:
            logger.debug("%s has no backend_node_id to scroll into view", self)
            return None
        try:
            await self.tab.send(
                cdp.dom.scroll_into_view_if_needed(
                    backend_node_id=self.backend_node_id,
                )
            )
        except RuntimeError as e:
            # Node may be detached or hidden, continue anyway
            logger.debug(
                "Could not scroll node %s into view", self.backend_node_id
            )
            logger.debug("Scroll error: %s", e)

    @tab_attached
    async def focus(
        self,
    ) -> None:
        """Set focus to the element.

        Suppresses errors if the element is not focusable.

        Raises:
            ReferenceError: If the tab session is no longer active.
        """
        if not self.backend_node_id:
            logger.debug("%s has no backend_node_id to focus", self)
            return None
        try:
            await self.tab.send(
                cdp.dom.focus(
                    backend_node_id=self.backend_node_id,
                )
            )
        except RuntimeError as e:
            # Node may not be focusable, continue anyway
            logger.debug("Could not focus node %s", self.backend_node_id)
            logger.debug("Focus error: %s", e)

    @tab_attached
    async def position(
        self,
    ) -> Position | None:
        """Get the position and coordinates of the element.

        Returns:
            Position | None: Container with element coordinates, or None if unavailable.

        Raises:
            ReferenceError: If the tab session is no longer active.
        """
        if not self.backend_node_id:
            logger.debug("%s has no backend_node_id to get position", self)
            return None
        quads: list[cdp.dom.Quad] = await self.tab.send(
            cdp.dom.get_content_quads(
                backend_node_id=self.backend_node_id,
            )
        )
        if quads:
            return Position(quad=quads[0])
        logger.debug("No quads returned for node %s", self.backend_node_id)
        return None

    @tab_attached
    async def click(
        self,
        button: cdp.input_.MouseButton = cdp.input_.MouseButton.LEFT,
        click_count: int = 1,
        delay: float = 0.02,
    ) -> Tab | None:
        """Click the element at its center point.

        Scrolls the element into view, calculates the center, and
        dispatches mouse press and release events. Returns the top-level
        tab, which is useful when the click triggers navigation.

        Args:
            button: Mouse button to use (default: LEFT).
            click_count: Number of clicks (1 for single, 2 for double).
            delay: Delay in seconds between press and release.

        Returns:
            Tab | None: The current top-level Tab containing this element,
                or None if the element position cannot be determined.

        Raises:
            ReferenceError: If the tab session is no longer active.

        Example:
            >>> link = await tab.wait_for_elem('a[href="/next"]')
            >>> current_tab = await link.click()
            >>> if current_tab:
            ...     await current_tab.wait_for_event(cdp.page.LoadEventFired)
            ...     print(f"Navigated to: {current_tab.url}")
        """
        await self.scroll_into_view()
        position = await self.position()
        if not position:
            logger.debug(
                "Could not get position for node %s", self.backend_node_id
            )
            return None
        x, y = position.center
        await self.tab.send(
            cdp.input_.dispatch_mouse_event(
                type_="mousePressed",
                x=x,
                y=y,
                button=button,
                click_count=click_count,
            )
        )
        await asyncio.sleep(delay)
        await self.tab.send(
            cdp.input_.dispatch_mouse_event(
                type_="mouseReleased",
                x=x,
                y=y,
                button=button,
                click_count=click_count,
            )
        )
        tab = self.tab
        while True:
            parent = tab.parent
            if parent is None:
                break
            tab = parent
        return tab

    @tab_attached
    async def type(
        self,
        text: str,
    ) -> None:
        """Type text into the element.

        Focuses the element and inserts the text via CDP input command.

        Args:
            text: The text string to type.

        Raises:
            ReferenceError: If the tab session is no longer active.
        """
        await self.scroll_into_view()
        await self.focus()
        await self.tab.send(cdp.input_.insert_text(text=text))

    @tab_attached
    async def set_value(
        self,
        value: str,
    ) -> None:
        """Set the value property of the element directly.

        Attempts to resolve the element to a RemoteObject and set its
        value property via JavaScript. This method also dispatches an
        'input' event to trigger any listeners. Falls back to typing
        character-by-character if resolution fails.

        This is faster than type() for setting form field values but may
        not trigger all the same events as real user typing.

        Args:
            value: The value to set.

        Raises:
            ReferenceError: If the tab session is no longer active.
        """
        obj = await self._resolve_object()
        if obj and obj.object_id:
            await self.tab.send(
                cdp.runtime.call_function_on(
                    object_id=obj.object_id,
                    function_declaration="function(v){ this.value = v; this.dispatchEvent(new Event('input', {bubbles:true})); }",
                    arguments=[cdp.runtime.CallArgument(value=value)],
                    await_promise=True,
                )
            )
        else:
            await self.type(value)

    @tab_attached
    async def text(
        self,
    ) -> Any:
        """Get the text content of the element.

        Returns:
            str | None: The text content, or None if unavailable.

        Raises:
            ReferenceError: If the tab session is no longer active.
        """
        obj = await self._resolve_object()
        if obj and obj.object_id:
            res, _ = await self.tab.send(
                cdp.runtime.call_function_on(
                    object_id=obj.object_id,
                    function_declaration="function(){ return this.textContent || ''; }",
                    await_promise=True,
                    return_by_value=True,
                )
            )
            return res.value
        return None

    @tab_attached
    async def html(
        self,
        include_shadow_dom: bool = True,
    ) -> Any:
        """Get the outer HTML of the element.

        Args:
            include_shadow_dom: Whether to include shadow DOM content.

        Returns:
            str: The outer HTML string.

        Raises:
            ReferenceError: If the tab session is no longer active.
        """
        res = await self.tab.send(
            cdp.dom.get_outer_html(
                backend_node_id=self.backend_node_id,
                include_shadow_dom=include_shadow_dom,
            )
        )
        return res

    @tab_attached
    async def attribute(
        self,
        name: str,
    ) -> str | None:
        """Get the value of an attribute.

        Args:
            name: The attribute name to retrieve.

        Returns:
            str | None: The attribute value, or None if not found.

        Raises:
            ReferenceError: If the tab session is no longer active.
        """
        attrs = await self.tab.send(
            cdp.dom.get_attributes(node_id=self.node_id)
        )
        attrs_list: list[str] = list(attrs)
        for i in range(0, len(attrs_list), 2):
            if attrs_list[i] == name:
                return attrs_list[i + 1]
        return None

    @tab_attached
    async def query_selector(
        self,
        selector: str,
    ) -> Elem | None:
        """Find a child element matching the selector.

        Args:
            selector: The CSS selector string.

        Returns:
            Elem | None: The found Elem or None if not found.

        Raises:
            ReferenceError: If the tab session is no longer active.
        """
        res = await self.tab.send(
            cdp.dom.query_selector(
                node_id=self.node_id,
                selector=selector,
            )
        )
        if res:
            node = await self.tab.send(cdp.dom.describe_node(node_id=res))
            return Elem(tab=self.tab, node=node)
        return None

    @tab_attached
    async def wait_for_selector(
        self,
        selector: str,
        timeout: float = 10.0,
        poll: float = 0.05,
    ) -> Elem | None:
        """Wait for a child element matching the selector to appear.

        Args:
            selector: CSS selector string.
            timeout: Maximum seconds to wait.
            poll: Polling interval in seconds.

        Returns:
            Elem | None: The matching element, or None if timeout.

        Raises:
            ReferenceError: If the tab session is no longer active.
        """
        end: float = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < end:
            el: Elem | None = await self.query_selector(selector)
            if el:
                return el
            await asyncio.sleep(poll)
        return None

    @tab_attached
    async def _resolve_object(
        self,
    ) -> cdp.runtime.RemoteObject | None:
        """Resolve the DOM node to a CDP RemoteObject.

        Returns:
            RemoteObject | None: The resolved object, or None if the
                node cannot be resolved.

        Raises:
            ReferenceError: If the tab session is no longer active.
        """
        try:
            res: cdp.runtime.RemoteObject = await self.tab.send(
                cdp.dom.resolve_node(
                    backend_node_id=self.backend_node_id,
                )
            )
            return res
        except RuntimeError:
            # Node cannot be resolved (detached, in different context, etc.)
            logger.debug(
                "Could not resolve node %s to RemoteObject",
                self.backend_node_id,
            )
            return None

    # Attributes--------------------------------------------------------------

    @property
    def parent(
        self,
    ) -> Elem | None:
        """Get the parent element of this Elem.

        Useful for traversing up the DOM tree. Can be chained to access
        ancestors: elem.parent.parent

        Example:
            # Navigate up to find a containing form
            button = await tab.find_elem("button[type=submit]")
            form = button.parent  # Get parent element
            while form and form.node_name != "FORM":
                form = form.parent

        Returns:
            Elem | None: The parent Elem, or None if this is a root element
                (no parent_id) or if the parent is the document root.
        """
        parent: Elem | None = None
        if self.node.parent_id:
            parent = self.tab.elem(node_id=self.node.parent_id)
        return parent

    def __repr__(
        self,
    ) -> str:
        """Get a string representation of the Elem.

        Returns:
            str: String representation of the Elem.
        """
        return f"<Elem node_id={self.node_id} backend_node_id={self.backend_node_id}>"

    def __getattr__(
        self,
        name: str,
    ) -> Any:
        """Delegate attribute access to node attributes.

        Args:
            name: The attribute name to access.
        Returns:
            Any: The attribute value from node.
        Raises:
            AttributeError: If the attribute is not found.
        """
        if self.node and hasattr(self.node, name):
            return getattr(self.node, name)
        raise AttributeError(f"'Elem' object has no attribute '{name}'")


__all__ = ["Elem", "Position"]
