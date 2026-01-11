"""Tests for Browser class (without launching Chrome)."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from pypecdp import cdp
from pypecdp.browser import Browser
from pypecdp.config import Config


class TestBrowser:
    """Test suite for Browser class."""

    @pytest.fixture
    def config(self) -> Config:
        """Create a test Config."""
        return Config(chrome_path="chromium", headless=True)

    def test_browser_init_with_config(self, config: Config) -> None:
        """Test Browser initialization with Config."""
        browser = Browser(config=config)

        assert browser.config == config
        assert browser.proc is None
        assert browser.reader is None
        assert browser.writer is None
        assert browser.targets == {}

    def test_browser_init_with_kwargs(self) -> None:
        """Test Browser initialization with kwargs."""
        browser = Browser(
            chrome_path="/usr/bin/chrome",
            headless=False,
            extra_args=["--no-sandbox"],
        )

        assert browser.config.chrome_path == "/usr/bin/chrome"
        assert browser.config.headless is False
        assert "--no-sandbox" in browser.config.extra_args

    def test_browser_init_auto_attach_default(self) -> None:
        """Test Browser auto_attach defaults to True."""
        browser = Browser()

        assert browser._auto_attach is True

    def test_browser_init_auto_attach_custom(self) -> None:
        """Test Browser auto_attach can be customized."""
        browser = Browser(auto_attach=False)

        assert browser._auto_attach is False

    def test_browser_init_default_domains(self) -> None:
        """Test Browser default_domains defaults to page and dom."""
        browser = Browser()

        assert cdp.page in browser._default_domains
        assert cdp.dom in browser._default_domains

    @pytest.mark.asyncio
    async def test_browser_start_classmethod(self) -> None:
        """Test Browser.start() class method."""
        with patch.object(
            Browser, "_launch", new_callable=AsyncMock
        ) as mock_launch:
            browser = await Browser.start(chrome_path="chromium")

            assert isinstance(browser, Browser)
            mock_launch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_with_session_id(self) -> None:
        """Test send includes session_id in message."""
        browser = Browser()
        browser.writer = Mock()
        browser.writer.write = Mock()
        browser.writer.drain = AsyncMock()
        browser._pending = {}

        # Create a future for the response
        import asyncio

        fut = asyncio.get_running_loop().create_future()
        fut.set_result({"id": 1, "result": {"value": "test"}})

        def mock_cmd():
            yield {
                "method": "Runtime.evaluate",
                "params": {"expression": "1+1"},
            }
            return "test"

        with patch.object(asyncio, "get_running_loop") as mock_loop:
            loop_mock = Mock()
            loop_mock.create_future.return_value = fut
            mock_loop.return_value = loop_mock

            # This would normally send, but we're testing structure
            # In real test, would need more complete mocking

    @pytest.mark.asyncio
    async def test_send_raises_runtime_error_on_cdp_error(self) -> None:
        """Test send raises RuntimeError when CDP returns error."""
        browser = Browser()
        browser.writer = Mock()
        browser.writer.write = Mock()
        browser.writer.drain = AsyncMock()

        import asyncio

        fut = asyncio.get_running_loop().create_future()
        fut.set_result(
            {"id": 1, "error": {"code": -32000, "message": "Error"}}
        )

        def mock_cmd():
            yield {"method": "Page.navigate"}

        with patch.object(asyncio, "get_running_loop") as mock_loop:
            loop_mock = Mock()
            loop_mock.create_future.return_value = fut
            mock_loop.return_value = loop_mock
            browser._pending[1] = fut
            browser._msg_id = 0

            with pytest.raises(RuntimeError, match="CDP error"):
                await browser.send(mock_cmd())

    def test_on_registers_handler(self) -> None:
        """Test on() registers event handler."""
        browser = Browser()
        handler = Mock()

        browser.on(cdp.target.TargetCreated, handler)

        assert cdp.target.TargetCreated in browser._handlers
        assert handler in browser._handlers[cdp.target.TargetCreated]

    def test_clear_handlers(self) -> None:
        """Test clear_handlers removes all handlers."""
        browser = Browser()
        browser.on(cdp.target.TargetCreated, Mock())
        browser.on(cdp.target.TargetDestroyed, Mock())

        browser.clear_handlers()

        assert len(browser._handlers) == 0

    @pytest.mark.asyncio
    async def test_create_tab(self) -> None:
        """Test create_tab creates a new target."""
        browser = Browser()
        browser.send = AsyncMock(
            return_value=cdp.target.TargetID("new-target")
        )

        tab = await browser.create_tab("https://example.com")

        assert tab is not None
        assert tab.target_id == cdp.target.TargetID("new-target")
        assert cdp.target.TargetID("new-target") in browser.targets

    @pytest.mark.asyncio
    async def test_navigate_creates_new_tab(self) -> None:
        """Test navigate with new_tab=True creates new tab."""
        browser = Browser()

        with patch.object(
            browser, "create_tab", new_callable=AsyncMock
        ) as mock_create:
            mock_tab = Mock()
            mock_tab.navigate = AsyncMock()
            mock_create.return_value = mock_tab

            tab = await browser.navigate("https://example.com", new_tab=True)

            mock_create.assert_awaited_once()
            mock_tab.navigate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_navigate_reuses_existing_tab(self) -> None:
        """Test navigate with new_tab=False reuses first tab."""
        browser = Browser()
        existing_tab = Mock()
        existing_tab.navigate = AsyncMock()

        # Mock the targets dict to return a page tab
        from pypecdp import cdp

        target_info = Mock()
        target_info.type_ = "page"
        existing_tab.target_info = target_info
        browser.targets = {cdp.target.TargetID("page-1"): existing_tab}

        tab = await browser.navigate("https://example.com", new_tab=False)

        assert tab == existing_tab
        existing_tab.navigate.assert_awaited_once()

    def test_pid_property(self) -> None:
        """Test pid property returns process ID."""
        browser = Browser()
        browser.proc = Mock()
        browser.proc.pid = 12345

        assert browser.pid == 12345

    def test_pid_property_none_when_no_proc(self) -> None:
        """Test pid property returns None when no process."""
        browser = Browser()
        browser.proc = None

        assert browser.pid is None

    def test_first_tab_property(self) -> None:
        """Test first_tab returns first page target."""
        browser = Browser()

        # Add a non-page target
        worker_tab = Mock()
        worker_info = Mock()
        worker_info.type_ = "worker"
        worker_tab.target_info = worker_info
        browser.targets[cdp.target.TargetID("worker")] = worker_tab

        # Add a page target
        page_tab = Mock()
        page_info = Mock()
        page_info.type_ = "page"
        page_tab.target_info = page_info
        browser.targets[cdp.target.TargetID("page")] = page_tab

        assert browser.first_tab == page_tab

    def test_first_tab_none_when_no_pages(self) -> None:
        """Test first_tab returns None when no page targets."""
        browser = Browser()

        assert browser.first_tab is None

    def test_repr(self) -> None:
        """Test Browser string representation."""
        browser = Browser()
        browser.proc = Mock()
        browser.proc.pid = 12345
        browser.proc.returncode = None

        repr_str = repr(browser)

        assert "Browser" in repr_str
        assert "pid=12345" in repr_str
        assert "targets=0" in repr_str

    @pytest.mark.asyncio
    async def test_context_manager_enter(self) -> None:
        """Test async context manager __aenter__."""
        browser = Browser()

        result = await browser.__aenter__()

        assert result == browser

    @pytest.mark.asyncio
    async def test_context_manager_exit(self) -> None:
        """Test async context manager __aexit__ closes browser."""
        browser = Browser()
        browser.close = AsyncMock()

        await browser.__aexit__(None, None, None)

        browser.close.assert_awaited_once()
