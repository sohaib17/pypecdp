"""Example: Quick start demonstration of basic pypecdp usage.

Demonstrates the minimal code to get started:
- Launching a browser instance
- Navigating to a URL
- Selecting and interacting with DOM elements
- Evaluating JavaScript in the page context
- Closing the browser
"""

import asyncio
import os

from pypecdp import Browser


async def main() -> None:
    """Main."""
    browser = await Browser.start(
        chrome_path=os.environ.get("PYPECDP_CHROME_PATH", "chromium"),
        headless=True,
        extra_args=["--no-sandbox"],
    )
    tab = await browser.navigate("https://example.com")
    h1 = await tab.wait_for_elem("h1")
    if h1:
        print("H1:", (await h1.html()).strip())
        parent = h1.parent
        if parent:
            print("H1 Parent:", (await parent.html()).strip())
        await h1.click()
    href = await tab.wait_for_elem('a[href*="example"]')
    if href:
        print("Text:", (await href.text()).strip())
        print("Link:", await href.attribute("href"))
    await tab.eval("console.log('hello from pypecdp')")
    await asyncio.sleep(0.5)
    await browser.close()


asyncio.run(main())
