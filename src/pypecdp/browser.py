"""High-level browser control and CDP message routing."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from types import ModuleType
from typing import Any, Callable

# Local CDP modules
from . import cdp
from .cdp.target import SessionID, TargetID
from .cdp_pipe import _Writer, launch_chrome_with_pipe
from .config import Config
from .logger import logger
from .tab import Tab


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
        config: Config | None = None,
        *,
        chrome_path: str = "chromium",
        user_data_dir: str | None = None,
        clean_data_dir: bool = True,
        headless: bool = True,
        extra_args: list[str] | None = None,
        ignore_default_args: list[str] | None = None,
        env: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Browser instance.

        Args:
            config: Pre-configured Config instance. If None, a new
                Config will be created from the keyword arguments.
            chrome_path: Path to Chrome/Chromium executable.
            user_data_dir: Path to user data directory. If None, a
                temporary directory will be created.
            headless: Whether to run in headless mode.
            extra_args: Additional command-line arguments.
            ignore_default_args: List of default args to ignore.
            env: Environment variables to set for browser process.
            **kwargs: Additional keyword arguments. Currently supports
                'auto_attach' to control automatic target attachment.
                'default_domains' to auto-enable CDP domains on a target.
        """
        self.config: Config = config or Config(
            chrome_path=chrome_path,
            user_data_dir=user_data_dir,
            clean_data_dir=clean_data_dir,
            headless=headless,
            extra_args=list(extra_args or []),
            ignore_default_args=ignore_default_args,
            env=dict(env or {}),
        )
        self.proc: asyncio.subprocess.Process | None = None
        self.reader: asyncio.StreamReader | None = None
        self.writer: _Writer | None = None
        self.targets: dict[TargetID, Tab] = {}
        self._msg_id: int = 0
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._recv_task: asyncio.Task[None] | None = None
        self._session_to_tab: dict[SessionID, Tab] = {}
        self._handlers: dict[type[Any], list[Callable[[Any], Any]]] = {}
        self._cursor: float = time.perf_counter()
        self._auto_attach: bool = kwargs.get("auto_attach", True)
        self._default_domains: list[ModuleType] = kwargs.get(
            "default_domains",
            [
                cdp.page,
                cdp.dom,
            ],
        )

    # Lifecycle --------------------------------------------------------------

    @classmethod
    async def start(
        cls,
        config: Config | None = None,
        **kwargs: Any,
    ) -> Browser:
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
    ) -> None:
        """Launch the Chrome browser process and initialize CDP connection.

        Sets up the browser subprocess, pipe communication, and enables
        target discovery.
        """
        self.proc, self.reader, self.writer = await launch_chrome_with_pipe(
            self.config
        )
        self._recv_task = asyncio.create_task(self._recv_loop())
        await self.send(
            cdp.target.set_discover_targets(
                discover=True,
            ),
        )
        await self

    async def close(
        self,
    ) -> None:
        """Close the browser and clean up resources.

        Closes all tabs, terminates the browser process, and cancels
        background tasks. This method handles cleanup gracefully:
        - Attempts graceful shutdown via CDP browser.close()
        - Falls back to SIGTERM if needed
        - Falls back to SIGKILL if process doesn't exit in 3 seconds

        Note:
            This method suppresses most errors to ensure cleanup completes
            even if the browser has already exited or crashed.
        """
        logger.info("Closing browser %s", self)
        try:
            await self.send(cdp.browser.close())
            with contextlib.suppress(asyncio.TimeoutError):
                if self.proc:
                    await asyncio.wait_for(self.proc.wait(), timeout=5)
        finally:
            if self.writer:
                try:
                    self.writer.close()
                except (OSError, RuntimeError):
                    logger.debug("Error closing writer")
            if self.proc and self.proc.returncode is None:
                try:
                    logger.debug("Terminating browser pid=%d", self.pid)
                    self.proc.terminate()
                    try:
                        await asyncio.wait_for(self.proc.wait(), timeout=3)
                    except asyncio.TimeoutError:
                        logger.warning("Timed out waiting for process to exit")
                        self.proc.kill()
                        await self.proc.wait()
                except (OSError, ProcessLookupError) as exc:
                    # Process may have already exited
                    logger.debug("Error terminating browser process")
                    logger.debug(exc)
            if self._recv_task:
                self._recv_task.cancel()
                try:
                    await self._recv_task
                except asyncio.CancelledError:
                    pass
            self.targets.clear()
            self._session_to_tab.clear()

    async def __aenter__(
        self,
    ) -> Browser:
        """Async context manager entry.

        Returns:
            Browser: This browser instance.
        """
        return self

    async def __aexit__(
        self,
        *args: Any,
    ) -> None:
        """Async context manager exit.

        Ensures the browser is properly closed when exiting the context.

        Args:
            *args: Exception info (exc_type, exc_val, exc_tb).
        """
        await self.close()

    # Messaging --------------------------------------------------------------

    async def send(
        self,
        cmd: Any,
        *,
        session_id: SessionID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Send a CDP command and await its response.

        Args:
            cmd: CDP command generator to send.
            session_id: Optional session ID for tab-specific commands.
            **kwargs: Optional keyword arguments:
                - ignore_errors (bool): If True, suppress CDP errors and
                  return None instead of raising RuntimeError.

        Returns:
            The parsed response from the CDP command, or None if
            ignore_errors=True and an error occurred.

        Raises:
            RuntimeError: If the CDP command returns an error and
                ignore_errors is False (default).
            ConnectionError: If the CDP pipe is closed.
        """
        ignore_errors = kwargs.get("ignore_errors", False)
        method, *params = next(cmd).values()
        payload: dict[str, Any] = params.pop() if params else {}
        self._msg_id += 1
        msg_id: int = self._msg_id
        msg: dict[str, Any] = {"id": msg_id, "method": method}
        if payload:
            msg["params"] = payload
        if session_id:
            msg["sessionId"] = str(session_id)

        fut: asyncio.Future[dict[str, Any]] = (
            asyncio.get_running_loop().create_future()
        )
        self._pending[msg_id] = fut

        assert self.writer is not None, "Browser not launched"
        raw: bytes = (json.dumps(msg, separators=(",", ":")) + "\0").encode(
            "utf-8"
        )
        self.writer.write(raw)
        await self.writer.drain()

        resp: dict[str, Any] = await fut
        if "error" in resp:
            err = resp["error"]
            if ignore_errors:
                logger.debug("Ignoring CDP error: %s", err)
                return None
            raise RuntimeError(f"CDP error {err})")

        # Send the result to the generator to get the parsed response
        result: dict[str, Any] = resp.get("result", {})
        try:
            cmd.send(result)
            raise RuntimeError("CDP generator did not exit as expected")
        except StopIteration as e:
            return e.value

    async def _recv_loop(
        self,
    ) -> None:
        """Receive and dispatch CDP messages from the browser.

        Continuously reads messages from the CDP pipe, resolves pending
        command futures, and dispatches events to tabs or browser-level
        handlers.
        """
        assert self.reader is not None
        while True:
            try:
                line: bytes = await self.reader.readuntil(separator=b"\0")
            except asyncio.IncompleteReadError:
                logger.debug("CDP pipe closed by browser")
                for fut in self._pending.values():
                    if not fut.done():
                        fut.set_exception(ConnectionError("CDP pipe closed"))
                self._pending.clear()
                break
            self._cursor = time.perf_counter()
            if not line:
                for fut in self._pending.values():
                    if not fut.done():
                        fut.set_exception(ConnectionError("CDP pipe closed"))
                self._pending.clear()
                return None

            try:
                msg: dict[str, Any] = json.loads(line[:-1])
            except Exception as exc:
                logger.exception("JSON parse error in CDP recv: %s", exc)
                continue

            if "id" in msg:
                msg_id: int = msg["id"]
                if msg_id in self._pending:
                    fut = self._pending.pop(msg_id)
                    if not fut.done():
                        fut.set_result(msg)
                continue

            # Parse event into typed CDP object
            try:
                event: Any = cdp.util.parse_json_event(msg)
            except (KeyError, AttributeError) as exc:
                # Event type not recognized or not registered
                logger.error(
                    "Could not parse event %s: %s - ignoring event",
                    msg.get("method"),
                    exc,
                )
                continue

            if "sessionId" in msg:
                session_id: SessionID = SessionID(msg["sessionId"])
                tab: Tab | None = self._session_to_tab.get(session_id)
                if tab:
                    await tab.handle_event(event)
            else:
                await self._handle_browser_event(event)

    async def _handle_browser_event(
        self,
        event: Any,
    ) -> None:
        """Handle browser-level CDP events.

        Processes target lifecycle events (creation, destruction,
        attachment) and dispatches other events to registered handlers.

        Args:
            event: CDP event object to handle.
        """
        tid: TargetID
        sid: SessionID
        method: type[Any] = type(event)
        if method == cdp.target.TargetCreated:
            # event is a TargetCreated object with target_info attribute
            logger.debug("Target created: %s", event)
            info = event.target_info
            tid = info.target_id
            typ: str = info.type_
            if tid and typ in {
                "page",
                "iframe",
                "worker",
                "shared_worker",
                "service_worker",
            }:
                self.targets.setdefault(tid, Tab(self, tid, info))
                if self._auto_attach:
                    asyncio.ensure_future(
                        self.send(
                            cdp.target.attach_to_target(
                                target_id=tid,
                                flatten=True,
                            ),
                            ignore_errors=True,
                        )
                    )

        elif method == cdp.target.TargetDestroyed:
            # event is a TargetDestroyed object with target_id attribute
            logger.debug("Target destroyed: %s", event)
            tid = event.target_id
            if tid:
                tab: Tab | None = self.targets.pop(tid, None)
                if tab and tab.session_id:
                    self._session_to_tab.pop(tab.session_id, None)
                    tab.session_id = None

        elif method == cdp.target.AttachedToTarget:
            # event is an AttachedToTarget object with session_id and target_info attributes
            logger.debug("Attached to target: %s", event)
            sid = event.session_id
            info = event.target_info
            tid = info.target_id
            if sid and tid:
                tab = self.targets.setdefault(tid, Tab(self, tid, info))
                tab.session_id = sid
                self._session_to_tab[sid] = tab
                if tab.type in {"page", "iframe"}:
                    for domain in self._default_domains:
                        asyncio.ensure_future(tab.send(domain.enable()))

        elif method == cdp.target.DetachedFromTarget:
            # event is a DetachedFromTarget object with session_id attribute
            logger.debug("Detached from target: %s", event)
            sid = event.session_id
            if sid:
                tab = self._session_to_tab.pop(sid, None)
                if tab:
                    tab.session_id = None

        elif method == cdp.target.TargetInfoChanged:
            # event is a TargetInfoChanged object with target_info attribute
            logger.debug("Target info changed: %s", event)
            info = event.target_info
            tid = info.target_id
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

    def clear_handlers(
        self,
    ) -> None:
        """Clear all registered event handlers for this browser."""
        self._handlers.clear()

    # User API ---------------------------------------------------------------

    async def create_tab(
        self,
        url: str = "about:blank",
    ) -> Tab:
        """Create a new tab and navigate to a URL.

        Args:
            url: The URL to navigate to in the new tab.
        Returns:
            Tab: The newly created tab.
        """
        target_id: TargetID = await self.send(
            cdp.target.create_target(
                url=url,
                new_window=False,
            )
        )
        tab = self.targets.setdefault(target_id, Tab(self, target_id, None))
        await asyncio.sleep(0.1)
        return tab

    async def navigate(
        self,
        url: str,
        new_tab: bool = False,
        timeout: float = 10.0,
    ) -> Tab:
        """Navigate to a URL in a tab.

        Args:
            url: The URL to navigate to.
            new_tab: If True, create a new tab. If False, reuse an
                existing tab if available.
            timeout: Maximum seconds to wait for page load.

        Returns:
            Tab: The tab that was navigated to the URL.
        """
        tab: Tab | None
        if not new_tab:
            tab = self.first_tab
            if tab:
                await tab.navigate(url, timeout=timeout)
                return tab
        # Create new target
        tab = await self.create_tab()
        await tab.navigate(url, timeout=timeout)
        return tab

    def on(
        self,
        event_name: type[Any],
        handler: Callable[[Any], Any],
    ) -> None:
        """Register an event handler for browser-level events.

        Args:
            event_name: The CDP event type to listen for.
            handler: Callback function or coroutine to handle the event.
        """
        self._handlers.setdefault(event_name, []).append(handler)

    # Attributes--------------------------------------------------------------

    def __repr__(
        self,
    ) -> str:
        """Get string representation of the Browser instance.

        Returns:
            str: String representation including process ID.
        """

        attrs = []
        attrs.append(f"pid={self.pid}")
        attrs.append(f"targets={len(self.targets)}")
        if self.proc and self.proc.returncode is not None:
            attrs.append(f"exited={self.proc.returncode}")
        return f"<Browser {' '.join(attrs)}>"

    def __await__(
        self,
    ) -> Any:
        """Make Browser awaitable to wait for CDP pipe idle state.

        Allows using 'await browser' to wait until the CDP message pipe
        has been idle (no messages) for a threshold period. Useful after
        browser launch to ensure all initial events have been processed.

        Example:
            browser = await Browser.start()
            await browser  # Wait for CDP pipe to be idle
            tab = await browser.navigate("https://example.com")

        Returns:
            Iterator that can be awaited.
        """
        return self._wait_idle().__await__()

    async def _wait_idle(
        self,
        threshold: float = 1.0,
        timeout: float = 5.0,
    ) -> None:
        """Check if the CDP pipe is idle (no recent messages).

        Args:
            threshold: Time in seconds with no messages to consider idle.
            timeout: Maximum time in seconds to wait.
        """
        start_time: float = time.perf_counter()
        while True:
            current_time: float = time.perf_counter()
            if current_time - self._cursor >= threshold:
                return None
            if (current_time - start_time) >= timeout:
                return None
            await asyncio.sleep(0.02)

    @property
    def pid(
        self,
    ) -> int | None:
        """Get the browser process ID.

        Returns:
            int: The process ID if the browser is running, else None.
        """
        if self.proc:
            return self.proc.pid
        return None

    @property
    def first_tab(
        self,
    ) -> Tab | None:
        """Get the first active tab.

        Returns:
            Tab: A Tab instance if one exists, else None.
        """
        for tab in self.targets.values():
            if tab.target_info and tab.target_info.type_ == "page":
                return tab
        return None


__all__ = ["Browser"]
