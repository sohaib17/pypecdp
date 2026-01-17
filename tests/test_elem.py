"""Tests for Elem class."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from pypecdp.cdp import dom
from pypecdp.elem import Elem, Position


class TestPosition:
    """Test suite for Position class."""

    def test_position_quad_properties(self) -> None:
        """Test Position calculates properties correctly from quad."""
        # Quad format: [x1, y1, x2, y2, x3, y3, x4, y4]
        # Top-left, top-right, bottom-right, bottom-left
        quad = [10.0, 20.0, 110.0, 20.0, 110.0, 70.0, 10.0, 70.0]
        pos = Position(quad=quad)

        assert pos.top_left == (10.0, 20.0)
        assert pos.top_right == (110.0, 20.0)
        assert pos.bottom_right == (110.0, 70.0)
        assert pos.bottom_left == (10.0, 70.0)

    def test_position_center(self) -> None:
        """Test Position calculates center correctly."""
        quad = [10.0, 20.0, 110.0, 20.0, 110.0, 70.0, 10.0, 70.0]
        pos = Position(quad=quad)

        # Center should be (60, 45)
        assert pos.center == (60.0, 45.0)

    def test_position_width_height(self) -> None:
        """Test Position calculates width and height."""
        quad = [10.0, 20.0, 110.0, 20.0, 110.0, 70.0, 10.0, 70.0]
        pos = Position(quad=quad)

        assert pos.width == 100.0
        assert pos.height == 50.0

    def test_position_repr(self) -> None:
        """Test Position string representation."""
        quad = [10.0, 20.0, 110.0, 20.0, 110.0, 70.0, 10.0, 70.0]
        pos = Position(quad=quad)

        repr_str = repr(pos)
        assert "Position" in repr_str
        assert "center=(60.0, 45.0)" in repr_str
        assert "width=100.0" in repr_str
        assert "height=50.0" in repr_str


class TestElem:
    """Test suite for Elem class."""

    @pytest.fixture
    def mock_tab(self) -> Mock:
        """Create a mock Tab."""
        tab = Mock()
        tab.target_id = "target-123"
        tab.session_id = "session-456"
        tab.send = AsyncMock()
        return tab

    @pytest.fixture
    def mock_node(self) -> Mock:
        """Create a mock DOM Node."""
        node = Mock()
        node.node_id = 1
        node.backend_node_id = 2
        node.node_type = 1
        node.node_name = "DIV"
        return node

    @pytest.fixture
    def elem(self, mock_tab: Mock, mock_node: Mock) -> Elem:
        """Create an Elem instance."""
        return Elem(tab=mock_tab, node=mock_node)

    def test_elem_creation(
        self, elem: Elem, mock_tab: Mock, mock_node: Mock
    ) -> None:
        """Test Elem can be created."""
        assert elem.tab == mock_tab
        assert elem.node == mock_node

    def test_elem_getattr_delegates_to_node(self, elem: Elem) -> None:
        """Test __getattr__ delegates to node."""
        assert elem.node_id == 1
        assert elem.backend_node_id == 2
        assert elem.node_type == 1
        assert elem.node_name == "DIV"

    def test_elem_getattr_raises_on_missing(self, mock_tab: Mock) -> None:
        """Test __getattr__ raises AttributeError for missing attributes."""
        # Create a node with spec to limit attributes
        node = Mock(
            spec=["node_id", "backend_node_id", "node_type", "node_name"]
        )
        node.node_id = 1
        node.backend_node_id = 2
        elem = Elem(tab=mock_tab, node=node)

        with pytest.raises(
            AttributeError,
            match="'Elem' object has no attribute 'nonexistent'",
        ):
            _ = elem.nonexistent

    def test_elem_repr(self, elem: Elem) -> None:
        """Test Elem string representation."""
        repr_str = repr(elem)
        assert "Elem" in repr_str
        assert "node_id=1" in repr_str
        assert "backend_node_id=2" in repr_str

    @pytest.mark.asyncio
    async def test_scroll_into_view_success(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test scroll_into_view sends correct command."""
        await elem.scroll_into_view()

        mock_tab.send.assert_called_once()
        # Verify the command is scroll_into_view_if_needed
        call_args = mock_tab.send.call_args[0][0]
        assert hasattr(call_args, "gi_frame") or hasattr(call_args, "cr_frame")

    @pytest.mark.asyncio
    async def test_scroll_into_view_no_backend_node_id(
        self, mock_tab: Mock, mock_node: Mock
    ) -> None:
        """Test scroll_into_view handles missing backend_node_id."""
        mock_node.backend_node_id = None
        elem = Elem(tab=mock_tab, node=mock_node)

        result = await elem.scroll_into_view()

        assert result is None
        mock_tab.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_scroll_into_view_suppresses_runtime_error(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test scroll_into_view suppresses RuntimeError."""
        mock_tab.send.side_effect = RuntimeError("Node detached")

        # Should not raise
        await elem.scroll_into_view()

    @pytest.mark.asyncio
    async def test_scroll_into_view_raises_reference_error_on_no_session(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test scroll_into_view raises ReferenceError when session is None."""
        mock_tab.session_id = None

        with pytest.raises(
            ReferenceError, match="Target .* is no longer available"
        ):
            await elem.scroll_into_view()

    @pytest.mark.asyncio
    async def test_focus_success(self, elem: Elem, mock_tab: Mock) -> None:
        """Test focus sends correct command."""
        await elem.focus()

        mock_tab.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_focus_suppresses_runtime_error(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test focus suppresses RuntimeError."""
        mock_tab.send.side_effect = RuntimeError("Not focusable")

        # Should not raise
        await elem.focus()

    @pytest.mark.asyncio
    async def test_position_returns_position_object(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test position returns Position object."""
        quad = [10.0, 20.0, 110.0, 20.0, 110.0, 70.0, 10.0, 70.0]
        mock_tab.send.return_value = [quad]

        pos = await elem.position()

        assert isinstance(pos, Position)
        assert pos.quad == quad

    @pytest.mark.asyncio
    async def test_position_returns_none_when_no_quads(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test position returns None when no quads available."""
        mock_tab.send.return_value = []

        pos = await elem.position()

        assert pos is None

    @pytest.mark.asyncio
    async def test_click_dispatches_mouse_events(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test click dispatches press and release events."""
        quad = [10.0, 20.0, 110.0, 20.0, 110.0, 70.0, 10.0, 70.0]
        mock_tab.send.return_value = [quad]
        mock_tab.parent = None  # Top-level tab

        result = await elem.click()

        # Should call send at least 3 times: get_content_quads, mousePressed, mouseReleased
        assert mock_tab.send.call_count >= 3
        # Should return the top-level tab
        assert result == mock_tab

    @pytest.mark.asyncio
    async def test_type_inserts_text(self, elem: Elem, mock_tab: Mock) -> None:
        """Test type inserts text."""
        quad = [10.0, 20.0, 110.0, 20.0, 110.0, 70.0, 10.0, 70.0]
        mock_tab.send.return_value = [quad]

        await elem.type("hello")

        # Should call send for scroll, focus, and insert_text
        assert mock_tab.send.call_count >= 3

    @pytest.mark.asyncio
    async def test_text_returns_text_content(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test text returns element text content."""
        remote_obj = Mock()
        remote_obj.object_id = "object-123"

        result_obj = Mock()
        result_obj.value = "Hello World"

        mock_tab.send.side_effect = [remote_obj, (result_obj, None)]

        text = await elem.text()

        assert text == "Hello World"

    @pytest.mark.asyncio
    async def test_html_returns_outer_html(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test html returns outer HTML."""
        mock_tab.send.return_value = "<div>Hello</div>"

        html = await elem.html()

        assert html == "<div>Hello</div>"

    @pytest.mark.asyncio
    async def test_attribute_returns_value(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test attribute returns attribute value."""
        mock_tab.send.return_value = ["class", "button", "id", "submit-btn"]

        value = await elem.attribute("class")

        assert value == "button"

    @pytest.mark.asyncio
    async def test_attribute_returns_none_when_not_found(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test attribute returns None when not found."""
        mock_tab.send.return_value = ["class", "button"]

        value = await elem.attribute("id")

        assert value is None

    @pytest.mark.asyncio
    async def test_query_selector_returns_elem(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test query_selector returns Elem."""
        node_id = 5
        child_node = Mock()
        child_node.node_id = node_id
        child_node.backend_node_id = 6

        mock_tab.send.side_effect = [node_id, child_node]

        result = await elem.query_selector("button")

        assert isinstance(result, Elem)
        assert result.node == child_node

    @pytest.mark.asyncio
    async def test_query_selector_returns_none_when_not_found(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test query_selector returns None when not found."""
        mock_tab.send.return_value = None

        result = await elem.query_selector("button")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_value_with_object_id(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test set_value sets value via RemoteObject."""
        remote_obj = Mock()
        remote_obj.object_id = "obj-123"

        mock_tab.send = AsyncMock(side_effect=[remote_obj, None])

        await elem.set_value("test value")

        assert mock_tab.send.call_count == 2

    @pytest.mark.asyncio
    async def test_set_value_falls_back_to_type(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test set_value falls back to type when no object_id."""
        remote_obj = Mock()
        remote_obj.object_id = None

        mock_tab.send = AsyncMock(
            side_effect=[
                remote_obj,  # resolve returns object without id
                None,  # scroll_into_view
                None,  # focus
                None,  # insert_text
            ]
        )

        await elem.set_value("test")

        # Should fall back to type method (scroll, focus, insert_text)
        assert mock_tab.send.call_count >= 3

    @pytest.mark.asyncio
    async def test_text_returns_none_when_no_object(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test text returns None when object cannot be resolved."""
        mock_tab.send = AsyncMock(side_effect=RuntimeError("Cannot resolve"))

        text = await elem.text()

        assert text is None

    @pytest.mark.asyncio
    async def test_wait_for_selector_finds_element(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test wait_for_selector finds element within timeout."""
        child_node = Mock()
        child_node.node_id = 5
        child_node.backend_node_id = 6

        # First call returns None, second returns node_id
        node_id = 5
        mock_tab.send = AsyncMock(side_effect=[None, node_id, child_node])

        result = await elem.wait_for_selector("button", timeout=1.0, poll=0.1)

        assert result is not None
        assert isinstance(result, Elem)

    @pytest.mark.asyncio
    async def test_wait_for_selector_returns_none_on_timeout(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test wait_for_selector returns None when element not found."""
        mock_tab.send = AsyncMock(return_value=None)

        result = await elem.wait_for_selector("button", timeout=0.1, poll=0.05)

        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_object_returns_none_on_error(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test _resolve_object handles RuntimeError."""
        mock_tab.send = AsyncMock(side_effect=RuntimeError("Node detached"))

        result = await elem._resolve_object()

        assert result is None

    @pytest.mark.asyncio
    async def test_focus_no_backend_node_id(self, mock_tab: Mock) -> None:
        """Test focus returns None when no backend_node_id."""
        node = Mock()
        node.backend_node_id = None
        elem = Elem(tab=mock_tab, node=node)

        result = await elem.focus()

        assert result is None
        mock_tab.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_position_no_backend_node_id(self, mock_tab: Mock) -> None:
        """Test position returns None when no backend_node_id."""
        node = Mock()
        node.backend_node_id = None
        elem = Elem(tab=mock_tab, node=node)

        result = await elem.position()

        assert result is None
        mock_tab.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_click_returns_none_when_no_position(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test click returns None when position cannot be obtained."""
        mock_tab.send = AsyncMock(
            side_effect=[None, []]
        )  # scroll, then empty quads

        result = await elem.click()

        assert result is None

    @pytest.mark.asyncio
    async def test_click_returns_top_level_tab_from_iframe(
        self, elem: Elem, mock_tab: Mock
    ) -> None:
        """Test click returns top-level tab when element is in an iframe."""
        quad = [10.0, 20.0, 110.0, 20.0, 110.0, 70.0, 10.0, 70.0]
        mock_tab.send.return_value = [quad]

        # Create parent tab hierarchy
        parent_tab = Mock()
        parent_tab.parent = None  # Top-level
        mock_tab.parent = parent_tab

        result = await elem.click()

        # Should return the top-level parent tab
        assert result == parent_tab

    def test_parent_returns_parent_elem_when_parent_id_exists(
        self, mock_tab: Mock
    ) -> None:
        """Test parent returns parent Elem when parent_id exists."""
        # Create parent node
        parent_node = Mock(
            spec=[
                "node_id",
                "backend_node_id",
                "node_type",
                "node_name",
                "parent_id",
            ]
        )
        parent_node.node_id = 10
        parent_node.backend_node_id = 20
        parent_node.node_type = 1
        parent_node.node_name = "BODY"
        parent_node.parent_id = None

        # Create child node with parent_id
        child_node = Mock(
            spec=[
                "node_id",
                "backend_node_id",
                "node_type",
                "node_name",
                "parent_id",
            ]
        )
        child_node.node_id = 1
        child_node.backend_node_id = 2
        child_node.node_type = 1
        child_node.node_name = "DIV"
        child_node.parent_id = 10

        # Mock tab.elem to return parent Elem
        parent_elem = Elem(tab=mock_tab, node=parent_node)
        mock_tab.elem = Mock(return_value=parent_elem)

        elem = Elem(tab=mock_tab, node=child_node)

        result = elem.parent

        assert result is not None
        assert isinstance(result, Elem)
        assert result.node == parent_node
        mock_tab.elem.assert_called_once_with(node_id=10)

    def test_parent_returns_none_when_no_parent_id(
        self, mock_tab: Mock
    ) -> None:
        """Test parent returns None when parent_id is None."""
        node = Mock(spec=["node_id", "backend_node_id", "parent_id"])
        node.node_id = 1
        node.backend_node_id = 2
        node.parent_id = None

        elem = Elem(tab=mock_tab, node=node)

        result = elem.parent

        assert result is None

    def test_parent_returns_none_when_parent_id_is_zero(
        self, mock_tab: Mock
    ) -> None:
        """Test parent returns None when parent_id is 0 (falsy)."""
        node = Mock(spec=["node_id", "backend_node_id", "parent_id"])
        node.node_id = 1
        node.backend_node_id = 2
        node.parent_id = 0

        elem = Elem(tab=mock_tab, node=node)

        result = elem.parent

        assert result is None

    def test_parent_property_can_be_accessed_multiple_times(
        self, mock_tab: Mock
    ) -> None:
        """Test parent property can be accessed multiple times."""
        parent_node = Mock(spec=["node_id", "backend_node_id", "parent_id"])
        parent_node.node_id = 10
        parent_node.backend_node_id = 20
        parent_node.parent_id = None

        child_node = Mock(spec=["node_id", "backend_node_id", "parent_id"])
        child_node.node_id = 1
        child_node.backend_node_id = 2
        child_node.parent_id = 10

        parent_elem = Elem(tab=mock_tab, node=parent_node)
        mock_tab.elem = Mock(return_value=parent_elem)

        elem = Elem(tab=mock_tab, node=child_node)

        # Access parent multiple times
        result1 = elem.parent
        result2 = elem.parent

        assert result1 is not None
        assert result2 is not None
        # Each access should call tab.elem
        assert mock_tab.elem.call_count == 2

    def test_parent_chain_traversal(self, mock_tab: Mock) -> None:
        """Test parent can be used to traverse up the DOM tree."""
        # Create a chain: grandparent -> parent -> child
        grandparent_node = Mock(
            spec=["node_id", "backend_node_id", "node_name", "parent_id"]
        )
        grandparent_node.node_id = 30
        grandparent_node.backend_node_id = 300
        grandparent_node.node_name = "HTML"
        grandparent_node.parent_id = None

        parent_node = Mock(
            spec=["node_id", "backend_node_id", "node_name", "parent_id"]
        )
        parent_node.node_id = 20
        parent_node.backend_node_id = 200
        parent_node.node_name = "BODY"
        parent_node.parent_id = 30

        child_node = Mock(
            spec=["node_id", "backend_node_id", "node_name", "parent_id"]
        )
        child_node.node_id = 10
        child_node.backend_node_id = 100
        child_node.node_name = "DIV"
        child_node.parent_id = 20

        # Create Elem instances
        grandparent_elem = Elem(tab=mock_tab, node=grandparent_node)
        parent_elem = Elem(tab=mock_tab, node=parent_node)
        child_elem = Elem(tab=mock_tab, node=child_node)

        # Mock tab.elem to return appropriate parent
        def mock_elem_lookup(node_id):
            if node_id == 20:
                return parent_elem
            elif node_id == 30:
                return grandparent_elem
            return None

        mock_tab.elem = Mock(side_effect=mock_elem_lookup)

        # Traverse from child to grandparent
        parent = child_elem.parent
        assert parent is not None
        assert parent.node_id == 20

        grandparent = parent.parent
        assert grandparent is not None
        assert grandparent.node_id == 30

        # Grandparent has no parent
        assert grandparent.parent is None
