"""Tests for util module."""

from unittest.mock import AsyncMock, Mock

import pytest

from pypecdp.elem import Elem
from pypecdp.util import tab_attached


class TestTabAttachedDecorator:
    """Test suite for @tab_attached decorator."""

    @pytest.fixture
    def mock_tab(self) -> Mock:
        """Create a mock Tab."""
        tab = Mock()
        tab.target_id = "target-123"
        tab.session_id = "session-456"
        return tab

    @pytest.fixture
    def mock_elem(self, mock_tab: Mock) -> Elem:
        """Create a mock Elem."""
        node = Mock()
        node.node_id = 1
        node.backend_node_id = 2
        return Elem(tab=mock_tab, node=node)

    @pytest.mark.asyncio
    async def test_decorator_allows_execution_when_session_active(
        self, mock_elem: Elem
    ) -> None:
        """Test decorator allows execution when session_id is not None."""

        @tab_attached
        async def test_method(self):
            return "success"

        result = await test_method(mock_elem)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_raises_reference_error_when_session_none(
        self, mock_elem: Elem
    ) -> None:
        """Test decorator raises ReferenceError when session_id is None."""
        mock_elem.tab.session_id = None

        @tab_attached
        async def test_method(self):
            return "should not execute"

        with pytest.raises(
            ReferenceError, match="Target .* is no longer available"
        ):
            await test_method(mock_elem)

    @pytest.mark.asyncio
    async def test_decorator_catches_session_not_found_error(
        self, mock_elem: Elem
    ) -> None:
        """Test decorator catches 'Session with given id not found' RuntimeError."""

        @tab_attached
        async def test_method(self):
            raise RuntimeError("Session with given id not found")

        with pytest.raises(
            ReferenceError, match="Target .* is no longer available"
        ):
            await test_method(mock_elem)

    @pytest.mark.asyncio
    async def test_decorator_preserves_other_runtime_errors(
        self, mock_elem: Elem
    ) -> None:
        """Test decorator doesn't catch other RuntimeErrors."""

        @tab_attached
        async def test_method(self):
            raise RuntimeError("Some other error")

        with pytest.raises(RuntimeError, match="Some other error"):
            await test_method(mock_elem)

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self) -> None:
        """Test decorator preserves function name and docstring."""

        @tab_attached
        async def test_method(self):
            """Test docstring."""
            pass

        assert test_method.__name__ == "test_method"
        assert test_method.__doc__ == "Test docstring."

    @pytest.mark.asyncio
    async def test_decorator_passes_args_and_kwargs(
        self, mock_elem: Elem
    ) -> None:
        """Test decorator passes through args and kwargs."""

        @tab_attached
        async def test_method(self, arg1, arg2, kwarg1=None):
            return f"{arg1}-{arg2}-{kwarg1}"

        result = await test_method(mock_elem, "a", "b", kwarg1="c")
        assert result == "a-b-c"

    @pytest.mark.asyncio
    async def test_decorator_with_no_return_value(
        self, mock_elem: Elem
    ) -> None:
        """Test decorator works with methods that return None."""

        @tab_attached
        async def test_method(self):
            pass

        result = await test_method(mock_elem)
        assert result is None
