"""Tests for util module."""

from unittest.mock import AsyncMock, Mock

import pytest

from pypecdp import cdp
from pypecdp.elem import Elem
from pypecdp.util import CookieJar, tab_attached


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


class TestCookieJar:
    """Test suite for CookieJar class."""

    @pytest.fixture
    def sample_cdp_cookie(self) -> cdp.network.Cookie:
        """Create a sample CDP cookie for testing."""
        return cdp.network.Cookie(
            name="test_cookie",
            value="test_value",
            domain=".example.com",
            path="/",
            size=20,
            http_only=True,
            secure=True,
            session=False,
            priority=cdp.network.CookiePriority.MEDIUM,
            source_scheme=cdp.network.CookieSourceScheme.SECURE,
            source_port=443,
            expires=1735689600.0,  # 2025-01-01 00:00:00 UTC
            same_site=cdp.network.CookieSameSite.STRICT,
        )

    @pytest.fixture
    def session_cdp_cookie(self) -> cdp.network.Cookie:
        """Create a session CDP cookie for testing."""
        return cdp.network.Cookie(
            name="session_cookie",
            value="session_value",
            domain="example.com",
            path="/app",
            size=25,
            http_only=False,
            secure=False,
            session=True,
            priority=cdp.network.CookiePriority.LOW,
            source_scheme=cdp.network.CookieSourceScheme.UNSET,
            source_port=-1,
            expires=-1.0,  # Session cookie
            same_site=None,
        )

    def test_cookiejar_initialization_empty(self) -> None:
        """Test CookieJar can be initialized empty."""
        jar = CookieJar()
        assert len(jar) == 0
        assert jar.cdp_cookies is None

    def test_cookiejar_initialization_with_cookies(
        self, sample_cdp_cookie: cdp.network.Cookie
    ) -> None:
        """Test CookieJar initializes with CDP cookies."""
        jar = CookieJar([sample_cdp_cookie])
        assert len(jar) == 1
        assert jar.cdp_cookies == [sample_cdp_cookie]

    def test_cookiejar_converts_cdp_cookie_attributes(
        self, sample_cdp_cookie: cdp.network.Cookie
    ) -> None:
        """Test CookieJar correctly converts CDP cookie attributes."""
        jar = CookieJar([sample_cdp_cookie])
        cookie = list(jar)[0]

        assert cookie.name == "test_cookie"
        assert cookie.value == "test_value"
        assert cookie.domain == ".example.com"
        assert cookie.path == "/"
        assert cookie.secure is True
        assert cookie._rest.get("HttpOnly") == "True"

    def test_cookiejar_handles_domain_initial_dot(
        self, sample_cdp_cookie: cdp.network.Cookie
    ) -> None:
        """Test CookieJar sets domain_initial_dot correctly."""
        jar = CookieJar([sample_cdp_cookie])
        cookie = list(jar)[0]
        assert cookie.domain_initial_dot is True

        # Test without leading dot
        sample_cdp_cookie.domain = "example.com"
        jar = CookieJar([sample_cdp_cookie])
        cookie = list(jar)[0]
        assert cookie.domain_initial_dot is False

    def test_cookiejar_handles_persistent_cookie_expiry(
        self, sample_cdp_cookie: cdp.network.Cookie
    ) -> None:
        """Test CookieJar handles persistent cookie expiry correctly."""
        jar = CookieJar([sample_cdp_cookie])
        cookie = list(jar)[0]

        assert cookie.discard is False
        assert cookie.expires == 1735689600
        assert isinstance(cookie.expires, int)

    def test_cookiejar_handles_session_cookie(
        self, session_cdp_cookie: cdp.network.Cookie
    ) -> None:
        """Test CookieJar handles session cookies correctly."""
        jar = CookieJar([session_cdp_cookie])
        cookie = list(jar)[0]

        assert cookie.name == "session_cookie"
        assert cookie.discard is True
        assert cookie.expires is None

    def test_cookiejar_handles_http_only_attribute(
        self, sample_cdp_cookie: cdp.network.Cookie
    ) -> None:
        """Test CookieJar stores HttpOnly in rest dict."""
        # HttpOnly = True
        sample_cdp_cookie.http_only = True
        jar = CookieJar([sample_cdp_cookie])
        cookie = list(jar)[0]
        assert cookie._rest.get("HttpOnly") == "True"

        # HttpOnly = False
        sample_cdp_cookie.http_only = False
        jar = CookieJar([sample_cdp_cookie])
        cookie = list(jar)[0]
        assert cookie._rest.get("HttpOnly") == "False"

    def test_cookiejar_handles_multiple_cookies(
        self,
        sample_cdp_cookie: cdp.network.Cookie,
        session_cdp_cookie: cdp.network.Cookie,
    ) -> None:
        """Test CookieJar handles multiple cookies."""
        jar = CookieJar([sample_cdp_cookie, session_cdp_cookie])
        assert len(jar) == 2
        assert len(jar.cdp_cookies) == 2

        cookie_names = {cookie.name for cookie in jar}
        assert cookie_names == {"test_cookie", "session_cookie"}

    def test_cookiejar_preserves_original_cdp_cookies(
        self, sample_cdp_cookie: cdp.network.Cookie
    ) -> None:
        """Test CookieJar preserves original CDP cookies."""
        jar = CookieJar([sample_cdp_cookie])

        assert jar.cdp_cookies is not None
        assert len(jar.cdp_cookies) == 1
        assert jar.cdp_cookies[0] is sample_cdp_cookie

        # CDP-specific attributes should be accessible
        assert jar.cdp_cookies[0].priority == cdp.network.CookiePriority.MEDIUM
        assert (
            jar.cdp_cookies[0].source_scheme
            == cdp.network.CookieSourceScheme.SECURE
        )
        assert (
            jar.cdp_cookies[0].same_site == cdp.network.CookieSameSite.STRICT
        )

    def test_cookiejar_inherits_from_standard_cookiejar(self) -> None:
        """Test CookieJar is a proper subclass of http.cookiejar.CookieJar."""
        from http import cookiejar as stdlib_cookiejar

        jar = CookieJar()
        assert isinstance(jar, stdlib_cookiejar.CookieJar)

    def test_cookiejar_handles_none_expires(self) -> None:
        """Test CookieJar handles None expires value."""
        cookie = cdp.network.Cookie(
            name="test",
            value="value",
            domain="example.com",
            path="/",
            size=10,
            http_only=False,
            secure=False,
            session=False,
            priority=cdp.network.CookiePriority.MEDIUM,
            source_scheme=cdp.network.CookieSourceScheme.UNSET,
            source_port=-1,
            expires=None,  # Unrepresentable value
        )

        jar = CookieJar([cookie])
        converted_cookie = list(jar)[0]
        assert converted_cookie.expires is None
        assert converted_cookie.discard is False  # Not a session cookie

    def test_cookiejar_cookie_version_is_netscape(
        self, sample_cdp_cookie: cdp.network.Cookie
    ) -> None:
        """Test CookieJar creates Netscape-style cookies (version 0)."""
        jar = CookieJar([sample_cdp_cookie])
        cookie = list(jar)[0]
        assert cookie.version == 0

    def test_cookiejar_cookie_domain_and_path_specified(
        self, sample_cdp_cookie: cdp.network.Cookie
    ) -> None:
        """Test CookieJar sets domain_specified and path_specified."""
        jar = CookieJar([sample_cdp_cookie])
        cookie = list(jar)[0]
        assert cookie.domain_specified is True
        assert cookie.path_specified is True
