"""DOM element wrapper and interactions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import cdp
from .cdp.dom import NodeId
from .cdp.input_ import MouseButton
from .cdp.runtime import CallArgument
from .logger import logger

if TYPE_CHECKING:
    from .tab import Tab


@dataclass
class Elem:
    """Wrapper for DOM elements with interaction methods.

    Provides high-level methods for interacting with elements in the
    browser, including clicking, typing, and retrieving attributes.

    Attributes:
        tab: The Tab instance containing this element.
        node_id: CDP NodeId identifying the DOM element.
    """

    tab: "Tab"
    node_id: NodeId

    async def _scroll_into_view(
        self,
    ) -> None:
        """Scroll element into viewport and attempt to focus it.

        Errors are suppressed if the element is detached or hidden.
        """
        try:
            await self.tab.send(
                cdp.dom.scroll_into_view_if_needed(node_id=self.node_id)
            )
        except RuntimeError:
            # Node may be detached or hidden, continue anyway
            logger.debug("Could not scroll node %s into view", self.node_id)

        try:
            await self.tab.send(cdp.dom.focus(node_id=self.node_id))
        except RuntimeError:
            # Node may not be focusable, continue anyway
            logger.debug("Could not focus node %s", self.node_id)

    async def _center_point(
        self,
    ) -> tuple[float, float]:
        """Calculate the center coordinates of the element's box model.

        Returns:
            tuple[float, float]: The (x, y) coordinates of the center.
        """
        box = await self.tab.send(cdp.dom.get_box_model(node_id=self.node_id))
        quad = box.content or box.border
        xs: list[float] = [quad[0], quad[2], quad[4], quad[6]]
        ys: list[float] = [quad[1], quad[3], quad[5], quad[7]]
        x: float = sum(xs) / 4.0
        y: float = sum(ys) / 4.0
        return float(x), float(y)

    async def click(
        self,
        button: MouseButton = MouseButton.LEFT,
        click_count: int = 1,
        delay: float = 0.02,
    ) -> None:
        """Click the element at its center point.

        Scrolls the element into view, calculates the center, and
        dispatches mouse press and release events.

        Args:
            button: Mouse button to use (default: LEFT).
            click_count: Number of clicks (1 for single, 2 for double).
            delay: Delay in seconds between press and release.
        """
        await self._scroll_into_view()
        x, y = await self._center_point()
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

    async def type(
        self,
        text: str,
    ) -> None:
        """Type text into the element.

        Focuses the element and inserts the text via CDP input command.

        Args:
            text: The text string to type.
        """
        await self.tab.send(cdp.dom.focus(node_id=self.node_id))
        await self.tab.send(cdp.input_.insert_text(text=text))

    async def set_value(
        self,
        value: str,
    ) -> None:
        """Set the value property of the element directly.

        Attempts to resolve the element to a RemoteObject and set its
        value property. Falls back to typing if resolution fails.

        Args:
            value: The value to set.
        """
        obj = await self._resolve_object()
        if obj and obj.object_id:
            await self.tab.send(
                cdp.runtime.call_function_on(
                    object_id=obj.object_id,
                    function_declaration="function(v){ this.value = v; this.dispatchEvent(new Event('input', {bubbles:true})); }",
                    arguments=[CallArgument(value=value)],
                    await_promise=True,
                )
            )
        else:
            await self.type(value)

    async def text(
        self,
    ) -> Any:
        """Get the text content of the element.

        Returns:
            str | None: The text content, or None if unavailable.
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

    async def html(
        self,
    ) -> Any:
        """Get the outer HTML of the element.

        Returns:
            str: The outer HTML string.
        """
        res = await self.tab.send(cdp.dom.get_outer_html(node_id=self.node_id))
        return res

    async def attribute(
        self,
        name: str,
    ) -> str | None:
        """Get the value of an attribute.

        Args:
            name: The attribute name to retrieve.

        Returns:
            str | None: The attribute value, or None if not found.
        """
        attrs = await self.tab.send(
            cdp.dom.get_attributes(node_id=self.node_id)
        )
        attrs_list: list[str] = list(attrs)
        for i in range(0, len(attrs_list), 2):
            if attrs_list[i] == name:
                return attrs_list[i + 1]
        return None

    async def _resolve_object(
        self,
    ) -> Any:
        """Resolve the DOM node to a CDP RemoteObject.

        Returns:
            RemoteObject | None: The resolved object, or None if the
                node cannot be resolved.
        """
        try:
            res = await self.tab.send(
                cdp.dom.resolve_node(node_id=self.node_id)
            )
            return res
        except RuntimeError:
            # Node cannot be resolved (detached, in different context, etc.)
            logger.debug(
                "Could not resolve node %s to RemoteObject", self.node_id
            )
            return None

    # Attributes--------------------------------------------------------------

    def __repr__(
        self,
    ) -> str:
        """Get a string representation of the Elem.

        Returns:
            str: String representation of the Elem.
        """
        return f"<Elem node_id={self.node_id}>"


__all__ = ["Elem"]
