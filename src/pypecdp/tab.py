"""Tab/session management and DOM utilities."""

import asyncio
import contextlib
import logging

from . import cdp
from .cdp.page import LoadEventFired

logger = logging.getLogger("pypecdp")


class Tab:

    def __init__(
        self,
        browser,
        target_id,
        target_info=None,
    ):
        self.browser = browser
        self.target_id = target_id
        self.target_info = target_info
        self.session_id = None
        self._handlers = {}

    async def init(
        self,
    ):
        await self.send(cdp.page.enable())
        await self.send(cdp.runtime.enable())
        await self.send(cdp.dom.enable())
        await self.send(cdp.log.enable())

    async def send(
        self,
        cmd,
    ):
        if not self.session_id:
            raise RuntimeError(f"Tab {self.target_id} not attached")
        return await self.browser.send(cmd, session_id=self.session_id)

    def on(
        self,
        event_name,
        handler,
    ):
        self._handlers.setdefault(event_name, []).append(handler)

    async def handle_event(
        self,
        event,
    ):
        method = type(event)
        for h in self._handlers.get(method, []):
            try:
                if asyncio.iscoroutinefunction(h) or asyncio.iscoroutine(h):
                    await h(event)
                else:
                    h(event)
            except Exception:
                logger.exception("Tab handler error for %s", method)

    # Navigation & evaluation ------------------------------------------------

    async def navigate(
        self,
        url,
        timeout=10.0,
    ):
        await self.send(cdp.page.navigate(url=url))
        if timeout > 0:
            await self.wait_for_event(event=LoadEventFired, timeout=timeout)

    async def wait_for_event(
        self,
        event=LoadEventFired,
        timeout=10.0,
    ):
        fut = asyncio.get_running_loop().create_future()

        async def on_loaded(_):
            if not fut.done():
                fut.set_result(None)
            # remove once fired
            handlers = self._handlers.get(event, [])
            if on_loaded in handlers:
                handlers.remove(on_loaded)

        self.on(event, on_loaded)
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(fut, timeout=timeout)

    async def eval(
        self,
        expression,
        await_promise=True,
    ):
        result, _ = await self.send(
            cdp.runtime.evaluate(
                expression=expression, await_promise=await_promise
            )
        )
        return result

    # DOM selection ----------------------------------------------------------

    async def select(
        self,
        selector,
    ):
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
        selector,
    ):
        root = await self.send(cdp.dom.get_document())
        node_id = root.node_id
        node_ids = await self.send(
            cdp.dom.query_selector_all(node_id=node_id, selector=selector)
        )
        return [Elem(self, nid) for nid in node_ids]

    async def wait_for_selector(
        self,
        selector,
        timeout=10.0,
        poll=0.05,
    ):
        end = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < end:
            el = await self.select(selector)
            if el:
                return el
            await asyncio.sleep(poll)
        return None

    async def close(
        self,
    ):
        try:
            await self.browser.send(
                cdp.target.close_target(target_id=self.target_id)
            )
        except (RuntimeError, ConnectionError):
            # Tab may already be closed or connection lost
            logger.debug("Could not close tab %s", self.target_id)


from .browser import Browser
from .elem import Elem
