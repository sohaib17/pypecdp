"""Example of clicking an element that causes navigation.

Demonstrates:
- Launching a browser instance
- Navigating to a URL
- Selecting a DOM element
- Clicking the element to navigate
- Waiting for the new page to load
- Printing the new page's URL and title
- Closing the browser
"""

import asyncio
import os

from pypecdp import Browser, Tab, cdp


async def main() -> None:
    """Main."""
    browser = await Browser.start(
        chrome_path=os.environ.get("PYPECDP_CHROME_PATH", "chromium"),
        headless=True,
    )
    tab = await browser.navigate("https://example.com/")
    href = await tab.wait_for_elem('a[href*="example"]')
    if href:
        current_tab: Tab | None = await href.click()
        # href elem is obsolete after navigation, so we use the returned tab
        if current_tab:
            await current_tab.wait_for_event(
                event=cdp.page.LoadEventFired,
                timeout=10.0,
            )
            print("Tab URL:", current_tab.url)
    await asyncio.sleep(0.5)
    await browser.close()


asyncio.run(main(), debug=True)
