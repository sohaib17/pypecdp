"""Tests for Tab class."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from pypecdp import cdp
from pypecdp.elem import Elem
from pypecdp.tab import Tab


class TestTab:
    """Test suite for Tab class."""

    @pytest.fixture
    def mock_browser(self) -> Mock:
        """Create a mock Browser."""
        browser = Mock()
        browser.send = AsyncMock()
        browser.targets = {}
        return browser

    @pytest.fixture
    def tab(self, mock_browser: Mock) -> Tab:
        """Create a Tab instance."""
        target_id = cdp.target.TargetID("target-123")
        target_info = Mock()
        target_info.type_ = "page"
        target_info.url = "https://example.com"
        target_info.title = "Example"
        target_info.target_id = target_id

        tab = Tab(mock_browser, target_id, target_info)
        tab.session_id = cdp.target.SessionID("session-456")
        return tab

    def test_tab_creation(self, tab: Tab, mock_browser: Mock) -> None:
        """Test Tab can be created."""
        assert tab.browser == mock_browser
        assert str(tab.target_id) == "target-123"
        assert str(tab.session_id) == "session-456"

    @pytest.mark.asyncio
    async def test_send_with_session(
        self, tab: Tab, mock_browser: Mock
    ) -> None:
        """Test send delegates to browser with session_id."""
        mock_browser.send.return_value = "result"

        # Create a mock command generator
        def mock_cmd():
            yield {
                "method": "Page.navigate",
                "params": {"url": "https://example.com"},
            }

        result = await tab.send(mock_cmd())

        mock_browser.send.assert_called_once()
        call_kwargs = mock_browser.send.call_args[1]
        assert call_kwargs["session_id"] == tab.session_id

    @pytest.mark.asyncio
    async def test_send_raises_when_not_attached(
        self, mock_browser: Mock
    ) -> None:
        """Test send raises RuntimeError when session_id is None."""
        target_id = cdp.target.TargetID("target-123")
        tab = Tab(mock_browser, target_id, None)
        tab.session_id = None

        def mock_cmd():
            yield {"method": "Page.navigate"}

        with pytest.raises(RuntimeError, match="not attached"):
            await tab.send(mock_cmd())

    def test_on_registers_handler(self, tab: Tab) -> None:
        """Test on registers event handler."""
        handler = Mock()

        tab.on(cdp.page.LoadEventFired, handler)

        assert cdp.page.LoadEventFired in tab._handlers
        assert handler in tab._handlers[cdp.page.LoadEventFired]

    @pytest.mark.asyncio
    async def test_handle_event_calls_sync_handler(self, tab: Tab) -> None:
        """Test handle_event calls synchronous handlers."""
        handler = Mock()
        event_class = type("MockEvent", (), {})
        tab.on(event_class, handler)

        event = event_class()
        await tab.handle_event(event)

        handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_handle_event_calls_async_handler(self, tab: Tab) -> None:
        """Test handle_event calls async handlers."""
        handler = AsyncMock()
        event_class = type("MockEvent", (), {})
        tab.on(event_class, handler)

        event = event_class()
        await tab.handle_event(event)

        handler.assert_awaited_once_with(event)

    @pytest.mark.asyncio
    async def test_handle_event_suppresses_exceptions(self, tab: Tab) -> None:
        """Test handle_event suppresses handler exceptions."""

        def bad_handler(event):
            raise ValueError("Handler error")

        event_class = type("MockEvent", (), {})
        tab.on(event_class, bad_handler)

        event = event_class()
        # Should not raise
        await tab.handle_event(event)

    def test_clear_handlers(self, tab: Tab) -> None:
        """Test clear_handlers removes all handlers."""
        tab.on(cdp.page.LoadEventFired, Mock())
        tab.on(cdp.runtime.ConsoleAPICalled, Mock())

        tab.clear_handlers()

        assert len(tab._handlers) == 0

    @pytest.mark.asyncio
    async def test_attach_creates_session(
        self, tab: Tab, mock_browser: Mock
    ) -> None:
        """Test attach creates a new session."""
        tab.session_id = None
        new_session_id = cdp.target.SessionID("new-session-789")
        mock_browser.send.return_value = new_session_id

        result = await tab.attach()

        assert result == new_session_id
        assert tab.session_id == new_session_id

    @pytest.mark.asyncio
    async def test_attach_returns_existing_session(
        self, tab: Tab, mock_browser: Mock
    ) -> None:
        """Test attach returns existing session if already attached."""
        existing_session = tab.session_id

        result = await tab.attach()

        assert result == existing_session
        mock_browser.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_navigate(self, tab: Tab, mock_browser: Mock) -> None:
        """Test navigate sends Page.navigate command."""
        frame_id = cdp.page.FrameId("frame-123")
        mock_browser.send.return_value = (frame_id, None)

        with patch.object(tab, "wait_for_event", new_callable=AsyncMock):
            await tab.navigate("https://example.com")

        assert tab._frameid == frame_id

    @pytest.mark.asyncio
    async def test_navigate_skips_wait_on_zero_timeout(
        self, tab: Tab, mock_browser: Mock
    ) -> None:
        """Test navigate skips wait_for_event when timeout is 0."""
        frame_id = cdp.page.FrameId("frame-123")
        mock_browser.send.return_value = (frame_id, None)

        await tab.navigate("https://example.com", timeout=0)

        # Just verify it completes without error

    @pytest.mark.asyncio
    async def test_eval(self, tab: Tab, mock_browser: Mock) -> None:
        """Test eval evaluates JavaScript."""
        remote_obj = Mock()
        remote_obj.type_ = "string"
        remote_obj.value = "test result"
        mock_browser.send.return_value = (remote_obj, None)

        result = await tab.eval("1 + 1")

        assert result == remote_obj

    @pytest.mark.asyncio
    async def test_find_elems_returns_list(
        self, tab: Tab, mock_browser: Mock
    ) -> None:
        """Test find_elems returns list of Elem."""
        # Mock the document
        doc_node = Mock()
        doc_node.children = []
        doc_node.shadow_roots = []

        search_id = "search-123"
        count = 2
        node_ids = [cdp.dom.NodeId(1), cdp.dom.NodeId(2)]

        mock_browser.send.side_effect = [
            doc_node,  # get_document
            (search_id, count),  # perform_search
            node_ids,  # get_search_results
            None,  # discard_search_results
        ]

        with patch.object(tab, "elem") as mock_elem:
            mock_elem.return_value = Mock(spec=Elem)
            results = await tab.find_elems("button")

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_find_elem_returns_first(self, tab: Tab) -> None:
        """Test find_elem returns first element."""
        elem1 = Mock(spec=Elem)
        elem2 = Mock(spec=Elem)

        with patch.object(
            tab, "find_elems", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = [elem1, elem2]

            result = await tab.find_elem("button")

        assert result == elem1

    @pytest.mark.asyncio
    async def test_find_elem_returns_none_when_empty(self, tab: Tab) -> None:
        """Test find_elem returns None when nothing found."""
        with patch.object(
            tab, "find_elems", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = []

            result = await tab.find_elem("button")

        assert result is None

    @pytest.mark.asyncio
    async def test_wait_for_elem_finds_element(self, tab: Tab) -> None:
        """Test wait_for_elem finds element within timeout."""
        elem = Mock(spec=Elem)

        with patch.object(
            tab, "wait_for_elems", new_callable=AsyncMock
        ) as mock_wait:
            mock_wait.return_value = [elem]

            result = await tab.wait_for_elem("button", timeout=1.0)

        assert result == elem

    @pytest.mark.asyncio
    async def test_wait_for_elem_returns_none_on_timeout(
        self, tab: Tab
    ) -> None:
        """Test wait_for_elem returns None on timeout."""
        with patch.object(
            tab, "wait_for_elems", new_callable=AsyncMock
        ) as mock_wait:
            mock_wait.return_value = []

            result = await tab.wait_for_elem("button", timeout=0.1)

        assert result is None

    @pytest.mark.asyncio
    async def test_close(self, tab: Tab, mock_browser: Mock) -> None:
        """Test close sends close_target command."""
        await tab.close()

        mock_browser.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_suppresses_errors(
        self, tab: Tab, mock_browser: Mock
    ) -> None:
        """Test close suppresses RuntimeError and ConnectionError."""
        mock_browser.send.side_effect = RuntimeError("Already closed")

        # Should not raise
        await tab.close()

    def test_repr(self, tab: Tab) -> None:
        """Test Tab string representation."""
        repr_str = repr(tab)

        assert "Tab" in repr_str
        assert "target-123" in repr_str
        assert "session-456" in repr_str

    def test_getattr_delegates_to_target_info(self, tab: Tab) -> None:
        """Test __getattr__ delegates to target_info."""
        assert tab.url == "https://example.com"
        assert tab.title == "Example"
        assert tab.type == "page"  # type -> type_

    def test_getattr_raises_on_missing(self) -> None:
        """Test __getattr__ raises AttributeError for missing attributes."""
        browser = Mock()
        target_id = cdp.target.TargetID("target-123")
        target_info = Mock(spec=["type_", "url", "title", "target_id"])
        target_info.type_ = "page"
        target_info.url = "https://example.com"
        target_info.title = "Example"
        target_info.target_id = target_id

        tab = Tab(browser, target_id, target_info)

        with pytest.raises(
            AttributeError, match="'Tab' object has no attribute"
        ):
            _ = tab.nonexistent

    @pytest.mark.asyncio
    async def test_wait_for_event_waits_and_fires(self, tab: Tab) -> None:
        """Test wait_for_event waits for an event to fire."""
        event_class = cdp.page.LoadEventFired

        # Simulate event firing after a short delay
        async def fire_event():
            await asyncio.sleep(0.05)
            event = event_class(timestamp=cdp.network.MonotonicTime(123.456))
            await tab.handle_event(event)

        # Run both concurrently
        task = asyncio.create_task(fire_event())
        await tab.wait_for_event(event_class, timeout=1.0)
        await task

        # Should complete without timeout

    @pytest.mark.asyncio
    async def test_wait_for_event_times_out(self, tab: Tab) -> None:
        """Test wait_for_event times out when event doesn't fire."""
        event_class = cdp.page.LoadEventFired

        # Should timeout quickly and not raise
        await tab.wait_for_event(event_class, timeout=0.1)

    @pytest.mark.asyncio
    async def test_elem_raises_when_doc_not_loaded(self, tab: Tab) -> None:
        """Test elem raises ValueError when document not loaded."""
        tab.doc = None

        with pytest.raises(ValueError, match="Tab document not loaded"):
            tab.elem(node_id=cdp.dom.NodeId(1))

    @pytest.mark.asyncio
    async def test_elem_raises_when_node_not_found(self, tab: Tab) -> None:
        """Test elem raises ValueError when node not found."""
        doc_node = Mock()
        doc_node.node_id = 0
        doc_node.children = []
        doc_node.shadow_roots = []
        tab.doc = doc_node

        with pytest.raises(ValueError, match="Node with id .* not found"):
            tab.elem(node_id=cdp.dom.NodeId(999))

    @pytest.mark.asyncio
    async def test_elem_finds_node_in_children(self, tab: Tab) -> None:
        """Test elem finds node in document children."""
        child_node = Mock()
        child_node.node_id = 5
        child_node.backend_node_id = 10
        child_node.children = []
        child_node.shadow_roots = []

        doc_node = Mock()
        doc_node.node_id = 0
        doc_node.children = [child_node]
        doc_node.shadow_roots = []
        tab.doc = doc_node

        result = tab.elem(node_id=cdp.dom.NodeId(5))

        assert result.node_id == 5
        assert result.backend_node_id == 10

    @pytest.mark.asyncio
    async def test_elem_finds_node_in_content_document(self, tab: Tab) -> None:
        """Test elem finds node in content document (iframe)."""
        target_node = Mock()
        target_node.node_id = 10
        target_node.backend_node_id = 20
        target_node.children = []
        target_node.shadow_roots = []

        content_doc = Mock()
        content_doc.node_id = 5
        content_doc.children = [target_node]
        content_doc.shadow_roots = []

        iframe_node = Mock()
        iframe_node.node_id = 2
        iframe_node.content_document = content_doc
        iframe_node.children = []
        iframe_node.shadow_roots = []

        doc_node = Mock()
        doc_node.node_id = 0
        doc_node.children = [iframe_node]
        doc_node.shadow_roots = []
        tab.doc = doc_node

        result = tab.elem(node_id=cdp.dom.NodeId(10))

        assert result.node_id == 10

    def test_frame_nodes_finds_iframes(
        self, tab: Tab, mock_browser: Mock
    ) -> None:
        """Test _frame_nodes finds iframe elements."""
        # Create iframe node
        iframe_node = Mock()
        iframe_node.node_name = "IFRAME"
        iframe_node.frame_id = cdp.page.FrameId("frame-123")
        iframe_node.children = []
        iframe_node.shadow_roots = []

        # Create doc with iframe
        doc_node = Mock()
        doc_node.children = [iframe_node]
        doc_node.shadow_roots = []

        # Mock browser targets
        frame_tab = Mock()
        mock_browser.targets = {cdp.target.TargetID("frame-123"): frame_tab}

        result = tab._frame_nodes(doc_node)

        assert len(result) == 1
        assert result[0] == frame_tab

    def test_frame_nodes_handles_missing_frame(
        self, tab: Tab, mock_browser: Mock
    ) -> None:
        """Test _frame_nodes handles iframe without target."""
        # Create iframe node with no matching target
        iframe_node = Mock()
        iframe_node.node_name = "IFRAME"
        iframe_node.frame_id = cdp.page.FrameId("unknown-frame")
        iframe_node.children = []
        iframe_node.shadow_roots = []

        doc_node = Mock()
        doc_node.children = [iframe_node]
        doc_node.shadow_roots = []

        mock_browser.targets = {}

        result = tab._frame_nodes(doc_node)

        assert len(result) == 0

    def test_frame_nodes_handles_no_frame_id(self, tab: Tab) -> None:
        """Test _frame_nodes handles iframe without frame_id."""
        iframe_node = Mock()
        iframe_node.node_name = "IFRAME"
        iframe_node.frame_id = None
        iframe_node.children = []
        iframe_node.shadow_roots = []

        doc_node = Mock()
        doc_node.children = [iframe_node]
        doc_node.shadow_roots = []

        result = tab._frame_nodes(doc_node)

        assert len(result) == 0

    def test_frame_nodes_recursive_search(
        self, tab: Tab, mock_browser: Mock
    ) -> None:
        """Test _frame_nodes searches recursively."""
        # Nested iframe
        nested_iframe = Mock()
        nested_iframe.node_name = "IFRAME"
        nested_iframe.frame_id = cdp.page.FrameId("nested-123")
        nested_iframe.children = []
        nested_iframe.shadow_roots = []

        # Parent div containing iframe
        div_node = Mock()
        div_node.node_name = "DIV"
        div_node.children = [nested_iframe]
        div_node.shadow_roots = []

        doc_node = Mock()
        doc_node.children = [div_node]
        doc_node.shadow_roots = []

        frame_tab = Mock()
        mock_browser.targets = {cdp.target.TargetID("nested-123"): frame_tab}

        result = tab._frame_nodes(doc_node)

        assert len(result) == 1
        assert result[0] == frame_tab

    def test_parent_property_returns_none_for_top_level(
        self, tab: Tab, mock_browser: Mock
    ) -> None:
        """Test that parent property returns None for top-level tabs."""
        # Top-level tab has no parent_frame_id
        tab.target_info.parent_frame_id = None

        parent = tab.parent

        assert parent is None

    def test_parent_property_returns_parent_tab(
        self, tab: Tab, mock_browser: Mock
    ) -> None:
        """Test that parent property returns parent tab for iframes."""
        # Create parent tab
        parent_target_id = cdp.target.TargetID("parent-target-789")
        parent_tab = Mock()
        mock_browser.targets[parent_target_id] = parent_tab

        # Set parent frame ID on child tab
        tab.target_info.parent_frame_id = "parent-target-789"

        parent = tab.parent

        assert parent == parent_tab

    def test_parent_property_returns_none_when_parent_not_found(
        self, tab: Tab, mock_browser: Mock
    ) -> None:
        """Test that parent property returns None when parent target not found."""
        # Set parent frame ID but don't add parent to targets
        tab.target_info.parent_frame_id = "nonexistent-parent"
        mock_browser.targets = {}

        parent = tab.parent

        assert parent is None
