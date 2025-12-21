"""High-level browser control and CDP message routing."""

import asyncio
import json
import logging
import os

# Local CDP modules
from . import cdp
from .cdp.target import TargetID
from .cdp_pipe import launch_chrome_with_pipe
from .config import Config

logger = logging.getLogger(os.environ.get("PYPECDP_LOGGER", "pypecdp"))


class Browser:
    """High-level browser automation via Chrome DevTools Protocol.

    Manages the Chrome/Chromium browser process lifecycle and CDP
    message routing between tabs and the browser.

    Attributes:
        config: Configuration object for browser launch.
        proc: The browser subprocess.
        reader: Stream reader for CDP pipe communication.
        writer: Stream writer for CDP pipe communication.
        targets: Mapping of target IDs to Tab instances.
    """

    def __init__(
        self,
        config=None,
        *,
        chrome_path="chromium",
        user_data_dir=None,
        headless=True,
        extra_args=None,
        switches=None,
        env=None,
    ):
        """Initialize Browser instance.

        Args:
            config: Pre-configured Config instance. If None, a new
                Config will be created from the keyword arguments.
            chrome_path: Path to Chrome/Chromium executable.
            user_data_dir: Path to user data directory. If None, a
                temporary directory will be created.
            headless: Whether to run in headless mode.
            extra_args: Additional command-line arguments.
            switches: Dictionary of Chrome switches to add.
            env: Environment variables to set for browser process.
        """
        self.config = config or Config(
            chrome_path=chrome_path,
            user_data_dir=user_data_dir,
            headless=headless,
            extra_args=list(extra_args or []),
            switches=dict(switches or {}),
            env=dict(env or {}),
        )
        self.proc = None
        self.reader = None
        self.writer = None
        self._msg_id = 0
        self._pending = {}
        self._recv_task = None
        self.targets = {}
        self._session_to_tab = {}
        self._handlers = {}

    # Lifecycle --------------------------------------------------------------

    @classmethod
    async def start(
        cls,
        config=None,
        **kwargs,
    ):
        """Start a new Browser instance.

        Args:
            config: Pre-configured Config instance. If None, a new
                Config will be created from kwargs.
            **kwargs: Arguments to pass to Config if config is None.

        Returns:
            Browser: An initialized and launched Browser instance.
        """

        browser = cls(config=config, **kwargs)
        await browser._launch()
        return browser

    async def _launch(
        self,
    ):
        """Launch the Chrome browser process and initialize CDP connection.

        Sets up the browser subprocess, pipe communication, and enables
        target discovery.
        """
        self.proc, self.reader, self.writer = await launch_chrome_with_pipe(
            self.config
        )
        self._recv_task = asyncio.create_task(self._recv_loop())
        await self.send(cdp.target.set_discover_targets(discover=True))

    async def close(
        self,
    ):
        """Close the browser and clean up resources.

        Closes all tabs, terminates the browser process, and cancels
        background tasks.
        """
        try:
            for tab in list(self.targets.values()):
                try:
                    await tab.close()
                except (RuntimeError, ConnectionError, asyncio.CancelledError):
                    # Tab may already be closed or connection lost
                    logger.debug("Could not close tab %s", tab.target_id)
        finally:
            if self.writer:
                try:
                    self.writer.close()
                except (OSError, RuntimeError):
                    logger.debug("Error closing writer")
            if self.proc and self.proc.returncode is None:
                try:
                    self.proc.terminate()
                    try:
                        await asyncio.wait_for(self.proc.wait(), timeout=3)
                    except asyncio.TimeoutError:
                        self.proc.kill()
                        await self.proc.wait()
                except (OSError, ProcessLookupError):
                    # Process may have already exited
                    logger.debug("Error terminating browser process")
            if self._recv_task:
                self._recv_task.cancel()
                try:
                    await self._recv_task
                except asyncio.CancelledError:
                    pass

    # Messaging --------------------------------------------------------------

    async def send(
        self,
        cmd,
        *,
        session_id=None,
    ):
        """Send a CDP command and await its response.

        Args:
            cmd: CDP command generator to send.
            session_id: Optional session ID for tab-specific commands.

        Returns:
            The parsed response from the CDP command.

        Raises:
            RuntimeError: If the CDP command returns an error.
            ConnectionError: If the CDP pipe is closed.
        """
        method, *params = next(cmd).values()
        payload = params.pop() if params else {}
        self._msg_id += 1
        msg_id = self._msg_id
        msg = {"id": msg_id, "method": method}
        if payload:
            msg["params"] = payload
        if session_id:
            msg["sessionId"] = str(session_id)

        fut = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = fut

        assert self.writer is not None, "Browser not launched"
        raw = (json.dumps(msg, separators=(",", ":")) + "\0").encode("utf-8")
        self.writer.write(raw)
        await self.writer.drain()

        resp = await fut
        if "error" in resp:
            err = resp["error"]
            raise RuntimeError(f"CDP error {err})")

        # Send the result to the generator to get the parsed response
        result = resp.get("result", {})
        try:
            cmd.send(result)
            raise RuntimeError("CDP generator did not exit as expected")
        except StopIteration as e:
            return e.value

    async def _recv_loop(
        self,
    ):
        """Receive and dispatch CDP messages from the browser.

        Continuously reads messages from the CDP pipe, resolves pending
        command futures, and dispatches events to tabs or browser-level
        handlers.
        """
        assert self.reader is not None
        while True:
            try:
                line = await self.reader.readuntil(separator=b"\0")
            except asyncio.IncompleteReadError:
                logger.info("CDP pipe closed by browser")
                for fut in self._pending.values():
                    if not fut.done():
                        fut.set_exception(ConnectionError("CDP pipe closed"))
                self._pending.clear()
                break
            if not line:
                for fut in self._pending.values():
                    if not fut.done():
                        fut.set_exception(ConnectionError("CDP pipe closed"))
                self._pending.clear()
                return None

            try:
                msg = json.loads(line[:-1])
            except Exception as exc:
                logger.exception("JSON parse error in CDP recv: %s", exc)
                continue

            if "id" in msg:
                msg_id = msg["id"]
                if msg_id in self._pending:
                    fut = self._pending.pop(msg_id)
                    if not fut.done():
                        fut.set_result(msg)
                continue

            # Parse event into typed CDP object
            method = msg.get("method")
            session_id = msg.get("sessionId")

            try:
                event = cdp.util.parse_json_event(msg)
            except (KeyError, AttributeError) as exc:
                # Event type not recognized or not registered
                logger.error(
                    "Could not parse event %s: %s - ignoring event",
                    method,
                    exc,
                )
                continue

            if session_id:
                tab = self._session_to_tab.get(session_id)
                if tab:
                    await tab.handle_event(event)
            else:
                await self._handle_browser_event(event)

    async def _handle_browser_event(
        self,
        event,
    ):
        """Handle browser-level CDP events.

        Processes target lifecycle events (creation, destruction,
        attachment) and dispatches other events to registered handlers.

        Args:
            event: CDP event object to handle.
        """
        method = type(event)
        if method == cdp.target.TargetCreated:
            # event is a TargetCreated object with target_info attribute
            info = event.target_info
            tid = str(info.target_id)
            typ = info.type_
            if tid and typ in {"page", "worker", "service_worker"}:
                self.targets.setdefault(tid, Tab(self, TargetID(tid), info))

        elif method == cdp.target.TargetDestroyed:
            # event is a TargetDestroyed object with target_id attribute
            tid = str(event.target_id)
            if tid:
                tab = self.targets.pop(tid, None)
                if tab and tab.session_id:
                    self._session_to_tab.pop(tab.session_id, None)

        elif method == cdp.target.AttachedToTarget:
            # event is an AttachedToTarget object with session_id and target_info attributes
            sid = str(event.session_id)
            tid = str(event.target_info.target_id)
            if sid and tid:
                tab = self.targets.setdefault(tid, Tab(self, TargetID(tid)))
                tab.session_id = sid
                self._session_to_tab[sid] = tab

        elif method == cdp.target.DetachedFromTarget:
            # event is a DetachedFromTarget object with session_id attribute
            sid = str(event.session_id)
            if sid:
                tab = self._session_to_tab.pop(sid, None)
                if tab:
                    tab.session_id = None

        elif method == cdp.target.TargetInfoChanged:
            # event is a TargetInfoChanged object with target_info attribute
            info = event.target_info
            tid = str(info.target_id)
            if tid:
                tab = self.targets.get(tid)
                if tab:
                    tab.target_info = info

        # Dispatch to registered browser-level handlers
        for h in self._handlers.get(method, []):
            try:
                if asyncio.iscoroutinefunction(h) or asyncio.iscoroutine(h):
                    await h(event)
                else:
                    h(event)
            except Exception:
                logger.exception("Browser handler error for %s", method)

    def clear_handlers(self):
        """Clear all registered event handlers for this browser."""
        self._handlers.clear()

    # User API ---------------------------------------------------------------

    async def get(
        self,
        url,
        new_tab=False,
    ):
        """Navigate to a URL in a tab.

        Args:
            url: The URL to navigate to.
            new_tab: If True, create a new tab. If False, reuse an
                existing tab if available.

        Returns:
            Tab: The tab that was navigated to the URL.
        """
        if not new_tab:
            # Try to find an existing tab with a page
            for tab in self.targets.values():
                if tab.target_info and tab.target_info.type_ == "page":
                    if not tab.session_id:
                        target_id = tab.target_id
                        # Attach to target and get session ID
                        tab.session_id = await self.send(
                            cdp.target.attach_to_target(
                                target_id=target_id,
                                flatten=True,
                            )
                        )
                        await tab.init()
                    await tab.navigate(url)
                    return tab

        # Create new target
        target_id = await self.send(
            cdp.target.create_target(url=url, new_window=False)
        )
        tid = str(target_id)
        tab = self.targets.setdefault(tid, Tab(self, target_id, None))
        # Attach to target and get session ID
        tab.session_id = await self.send(
            cdp.target.attach_to_target(
                target_id=target_id,
                flatten=True,
            )
        )
        # Initialize tab
        await tab.init()
        await tab.navigate(url)
        return tab

    def on(
        self,
        event_name,
        handler,
    ):
        """Register an event handler for browser-level events.

        Args:
            event_name: The CDP event type to listen for.
            handler: Callback function or coroutine to handle the event.
        """
        self._handlers.setdefault(event_name, []).append(handler)


from .tab import Tab
