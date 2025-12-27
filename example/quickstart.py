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
    h1 = await tab.select("h1")
    if h1:
        print("H1:", (await h1.text()).strip())
        await h1.click()
    await tab.eval("console.log('hello from pypecdp')")
    await asyncio.sleep(0.5)
    await browser.close()


asyncio.run(main())
