"""Example: Multi-tab workflow and coordination.

Demonstrates managing multiple browser tabs concurrently:
- Creating multiple tabs with browser.navigate(new_tab=True)
- Tracking active tabs in Browser.targets dictionary
- Coordinating actions across multiple tabs
- Running parallel operations on different tabs
- Tab lifecycle management and selective tab closure
"""

import asyncio
import os
from typing import Any

from pypecdp import Browser


async def main() -> None:
    """Main."""
    # Launch browser
    browser = await Browser.start(
        chrome_path=os.environ.get("PYPECDP_CHROME_PATH", "chromium"),
        headless=True,
        extra_args=["--no-sandbox"],
    )
    print("Browser launched\n")

    # Example 1: Sequential tab creation
    print("=" * 60)
    print("Example 1: Creating multiple tabs sequentially")
    print("=" * 60)

    tabs = []
    urls = [
        "https://example.com",
        "https://example.org",
        "https://www.iana.org/domains/reserved",
    ]

    for i, url in enumerate(urls, 1):
        print(f"Creating tab {i}: {url}")
        tab = await browser.navigate(url, new_tab=True)
        tabs.append(tab)
        await asyncio.sleep(0.5)  # Small delay for demonstration

    print(f"\nCreated {len(tabs)} tabs")
    print(f"Browser has {len(browser.targets)} total targets")

    # Extract titles from all tabs
    print("\n" + "=" * 60)
    print("Example 2: Extracting data from all tabs")
    print("=" * 60)

    for i, tab in enumerate(tabs, 1):
        # Get page title
        result = await tab.eval("document.title")
        title = result.value if result and result.value else "Unknown"
        print(f"Tab {i}: {title}")

    # Example 3: Parallel operations
    print("\n" + "=" * 60)
    print("Example 3: Parallel operations across tabs")
    print("=" * 60)

    async def get_h1_text(tab: Any, tab_num: int) -> str:
        """Extract h1 text from a tab."""
        h1 = await tab.find_elem("h1")
        if h1:
            text = await h1.text()
            return f"Tab {tab_num}: {text.strip()}"
        return f"Tab {tab_num}: No h1 found"

    # Run in parallel
    print("Extracting h1 elements in parallel...")
    results = await asyncio.gather(
        *[get_h1_text(tab, i) for i, tab in enumerate(tabs, 1)]
    )

    for el_text in results:
        print(f"  {el_text}")

    # Example 4: Cross-tab coordination
    print("\n" + "=" * 60)
    print("Example 4: Cross-tab data sharing via JavaScript")
    print("=" * 60)

    # Set some data in first tab
    await tabs[0].eval('window.myData = "Hello from tab 1"')
    print("Set data in tab 1")

    # Try to access it from second tab (will fail - different contexts)
    result = await tabs[1].eval("typeof window.myData")
    data_type = result.value if result and result.value else "unknown"
    print(f"Data type in tab 2: {data_type} (isolated contexts)")

    # Example 5: Closing specific tabs
    print("\n" + "=" * 60)
    print("Example 5: Selective tab closure")
    print("=" * 60)

    print(f"Targets before closing: {len(browser.targets)}")

    # Close the second tab
    print("Closing tab 2...")
    await tabs[1].close()
    await asyncio.sleep(0.5)  # Wait for cleanup

    print(f"Targets after closing tab 2: {len(browser.targets)}")

    # Verify first and third tabs still work
    print("\nVerifying remaining tabs still work:")
    for i, tab in zip([1, 3], [tabs[0], tabs[2]]):
        try:
            result = await tab.eval("document.title")
            title = result.value if result and result.value else "Unknown"
            print(f"  Tab {i}: {title} - OK")
        except Exception as e:
            print(f"  Tab {i}: ERROR - {e}")

    # Example 6: Opening new tabs after initial batch
    print("\n" + "=" * 60)
    print("Example 6: Dynamic tab creation")
    print("=" * 60)

    print("Opening a new tab dynamically...")
    _ = await browser.navigate("https://httpbin.org/html")
    await asyncio.sleep(0.5)

    print(f"Total targets now: {len(browser.targets)}")

    # List all current target IDs and types
    print("\nAll current targets:")
    for target_id, tab in browser.targets.items():
        print(f"  {target_id}... -> {tab}")

    # Clean up all tabs
    print("\n" + "=" * 60)
    print("Cleanup")
    print("=" * 60)

    print("Closing all tabs and browser...")
    await browser.close()
    print("Browser closed")
    print(f"Remaining targets: {len(browser.targets)}")


if __name__ == "__main__":
    asyncio.run(main())
