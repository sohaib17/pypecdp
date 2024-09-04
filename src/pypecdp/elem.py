"""DOM element wrapper and interactions."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from . import cdp
from .cdp.dom import NodeId
from .cdp.input_ import MouseButton
from .cdp.runtime import CallArgument

logger = logging.getLogger("pypecdp")


@dataclass
class Elem:

    tab: "Tab"
    node_id: NodeId

    async def _scroll_into_view(
        self,
    ):
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
    ):
        box = await self.tab.send(cdp.dom.get_box_model(node_id=self.node_id))
        quad = box.content or box.border
        xs = [quad[0], quad[2], quad[4], quad[6]]
        ys = [quad[1], quad[3], quad[5], quad[7]]
        x = sum(xs) / 4.0
        y = sum(ys) / 4.0
        return float(x), float(y)

    async def click(
        self,
        button=MouseButton.LEFT,
        click_count=1,
        delay=0.02,
    ):
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
        text,
    ):
        await self.tab.send(cdp.dom.focus(node_id=self.node_id))
        await self.tab.send(cdp.input_.insert_text(text=text))

    async def set_value(
        self,
        value,
    ):
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
    ):
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
    ):
        res = await self.tab.send(cdp.dom.get_outer_html(node_id=self.node_id))
        return res

    async def attribute(
        self,
        name,
    ):
        attrs = await self.tab.send(
            cdp.dom.get_attributes(node_id=self.node_id)
        )
        attrs_list = list(attrs)
        for i in range(0, len(attrs_list), 2):
            if attrs_list[i] == name:
                return attrs_list[i + 1]
        return None

    async def _resolve_object(
        self,
    ):
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


from .tab import Tab
