"""Example: Network interception using CDP Fetch domain.

Demonstrates network request interception and modification:
- Enabling Fetch domain for network interception
- Intercepting HTTP requests with Fetch.requestPaused events
- Modifying request headers before forwarding
- Blocking specific resources like images and stylesheets
- Mocking API responses with custom data
"""

import asyncio
import base64
import os
from typing import Any

from pypecdp import Browser, cdp
from pypecdp.cdp.fetch import HeaderEntry, RequestPattern, RequestStage
from pypecdp.cdp.network import ErrorReason, ResourceType


async def main() -> None:
    """Main."""
    # Launch browser
    browser = await Browser.start(
        chrome_path=os.environ.get("PYPECDP_CHROME_PATH", "chromium"),
        headless=True,
        extra_args=["--no-sandbox"],
    )

    tab = await browser.navigate("about:blank")
    print("Browser launched and tab created")

    # Enable Fetch domain for request interception
    print("\nEnabling Fetch domain...")
    await tab.send(
        cdp.fetch.enable(
            patterns=[
                RequestPattern(
                    url_pattern="*",
                    request_stage=RequestStage.REQUEST,
                ),
            ]
        )
    )

    # Counter for intercepted requests
    intercepted_count = {"total": 0, "blocked": 0, "modified": 0}

    # Handler for Fetch.requestPaused events
    async def handle_request(event: Any) -> None:
        # event is a RequestPaused object with attributes
        request_id = event.request_id
        request = event.request
        url = request.url
        resource_type = event.resource_type

        intercepted_count["total"] += 1

        # Block images and stylesheets
        if resource_type in (ResourceType.IMAGE, ResourceType.STYLESHEET):
            print(f"[x] Blocking {resource_type}: {url}")
            intercepted_count["blocked"] += 1
            asyncio.ensure_future(
                tab.send(
                    cdp.fetch.fail_request(
                        request_id=request_id,
                        error_reason=ErrorReason.BLOCKED_BY_CLIENT,
                    )
                )
            )
            return None

        # Modify request headers for other resources
        if resource_type in (ResourceType.DOCUMENT, ResourceType.XHR):
            headers_dict = dict(request.headers)
            headers_dict["X-Custom-Header"] = "pypecdp-example"
            headers_dict["User-Agent"] = "pypecdp/1.0 (Custom Bot)"
            headers: list[HeaderEntry] = [
                HeaderEntry(name=k, value=v) for k, v in headers_dict.items()
            ]

            print(f"[+] Modifying headers for {resource_type}: {url}")
            intercepted_count["modified"] += 1

            asyncio.ensure_future(
                tab.send(
                    cdp.fetch.continue_request(
                        request_id=request_id,
                        headers=headers,
                    )
                )
            )
            return None

        # Continue all other requests normally
        asyncio.ensure_future(
            tab.send(
                cdp.fetch.continue_request(
                    request_id=request_id,
                ),
            )
        )

    # Register the event handler
    tab.on(cdp.fetch.RequestPaused, handle_request)

    # Navigate to a page - interception will happen automatically
    print("\nNavigating to example.com (images will be blocked)...")
    await tab.navigate("https://example.com")

    # Wait for page to finish loading
    await asyncio.sleep(2)

    print("\nInterception summary:")
    print(f"  Total requests intercepted: {intercepted_count['total']}")
    print(f"  Blocked: {intercepted_count['blocked']}")
    print(f"  Modified: {intercepted_count['modified']}")
    unchanged = (
        intercepted_count["total"]
        - intercepted_count["blocked"]
        - intercepted_count["modified"]
    )
    print(f"  Continued unchanged: {unchanged}")

    # Example 2: Mock a specific response
    print("\n" + "=" * 60)
    print("Example 2: Mocking a JSON API response")
    print("=" * 60)

    # Disable previous pattern
    await tab.send(cdp.fetch.disable())

    # Enable with new pattern for specific URL
    await tab.send(
        cdp.fetch.enable(
            patterns=[
                RequestPattern(
                    url_pattern="*httpbin.org/json*",
                    request_stage=RequestStage.REQUEST,
                ),
            ]
        )
    )

    # New handler for mocking
    async def mock_json_response(event: Any) -> None:
        # event is a RequestPaused object with attributes
        request_id = event.request_id
        request = event.request
        url = request.url

        if "httpbin.org/json" in url:
            print(f"Mocking response for: {url}")

            # Create mock JSON response
            mock_data = b'{"mocked": true, "message": "Mocked by pypecdp!"}'
            headers = [
                HeaderEntry(name="Content-Type", value="application/json"),
                HeaderEntry(name="X-Mocked-By", value="pypecdp"),
            ]
            # Fulfill with mock response
            asyncio.ensure_future(
                tab.send(
                    cdp.fetch.fulfill_request(
                        request_id=request_id,
                        response_code=200,
                        response_headers=headers,
                        body=base64.b64encode(mock_data).decode("ascii"),
                    )
                )
            )
        else:
            asyncio.ensure_future(
                tab.send(
                    cdp.fetch.continue_request(
                        request_id=request_id,
                    ),
                )
            )

    # Clear old handler and register new one
    tab.clear_handlers()
    tab.on(cdp.fetch.RequestPaused, mock_json_response)

    # Navigate to trigger the mock
    await tab.navigate("https://httpbin.org/json")
    await asyncio.sleep(1)

    # Check the page content
    result = await tab.eval("document.body.textContent")
    if result and result.value:
        content = result.value
        print(f"\nPage content: {content}")
        if "mocked" in content:
            print("Successfully mocked the response!")

    # Clean up
    await browser.close()
    print("\nBrowser closed")


if __name__ == "__main__":
    asyncio.run(main())
