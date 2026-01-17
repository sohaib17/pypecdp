"""Example: Customize pypecdp using OOP inheritance.

Demonstrates how to extend pypecdp classes with custom functionality.
"""

import asyncio
import os

from pypecdp import Browser, Elem, Tab, cdp


# Custom Elem with additional methods
class MyElem(Elem):
    """Custom element with click_and_wait method."""

    async def click_and_wait(self, timeout: float = 10.0) -> None:
        """Click element and wait for navigation."""
        tab = await self.click()
        if tab:
            await tab.wait_for_event(cdp.page.LoadEventFired, timeout=timeout)
            print(f"Navigated to: {tab.url}")


# Custom Tab using custom Elem
class MyTab(Tab):
    """Custom tab with helper methods."""

    elem_class = MyElem  # Use our custom Elem class

    async def get_title(self) -> str:
        """Get page title via JavaScript."""
        result = await self.eval("document.title")
        return result.value if result.value else ""


# Custom Browser using custom Tab
class MyBrowser(Browser):
    """Custom browser with helper methods."""

    tab_class = MyTab  # Use our custom Tab class

    async def navigate_and_log(self, url: str) -> Tab:
        """Navigate with logging."""
        print(f"Navigating to: {url}")
        tab = await self.navigate(url)
        print(f"Loaded: {url}")
        return tab


async def main() -> None:
    """Demonstrate custom classes."""
    # Use custom browser
    browser = await MyBrowser.start(
        chrome_path=os.environ.get("PYPECDP_CHROME_PATH", "chromium"),
        headless=True,
    )

    # All tabs will be MyTab instances
    tab = await browser.navigate_and_log("https://example.com")
    print(f"Title: {await tab.get_title()}")

    # All elements will be MyElem instances
    link = await tab.wait_for_elem('a[href*="iana"]')
    if link:
        # Use custom click_and_wait method
        await link.click_and_wait()

    await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
