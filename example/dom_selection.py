"""Example: Advanced DOM selection and element manipulation.

Demonstrates various DOM query and manipulation techniques:
- Tab.find_elem() for single element selection with CSS selectors
- Tab.find_elems() for multiple element selection
- Tab.wait_for_elem() for dynamic content that appears after page load
- Element attribute extraction using Elem.attribute()
- Element text content retrieval using Elem.text()
- Element HTML serialization using Elem.html()
- Complex CSS selectors and nested element traversal
"""

import asyncio
import base64
import os

from pypecdp import Browser


async def main() -> None:
    """Main."""
    # Launch browser
    browser = await Browser.start(
        chrome_path=os.environ.get("PYPECDP_CHROME_PATH", "chromium"),
        headless=True,
        extra_args=["--no-sandbox"],
    )

    # Create a complex test page
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DOM Selection Test</title>
        <style>
            .container { padding: 20px; }
            .item { margin: 10px 0; }
            .highlight { background: yellow; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 id="main-title" data-test="title">DOM Selection Examples</h1>
            
            <div class="item" data-id="1">
                <h2>Item 1</h2>
                <p class="description">First item description</p>
                <a href="https://example.com/1" class="link">Link 1</a>
            </div>
            
            <div class="item" data-id="2">
                <h2>Item 2</h2>
                <p class="description">Second item description</p>
                <a href="https://example.com/2" class="link">Link 2</a>
            </div>
            
            <div class="item" data-id="3">
                <h2>Item 3</h2>
                <p class="description">Third item description</p>
                <a href="https://example.com/3" class="link">Link 3</a>
            </div>
            
            <ul id="feature-list">
                <li class="feature">Feature A</li>
                <li class="feature highlight">Feature B (highlighted)</li>
                <li class="feature">Feature C</li>
            </ul>
            
            <div id="async-content" style="display:none;">
                This content will appear after 1 second
            </div>
        </div>
        
        <script>
            // Simulate async content loading
            setTimeout(() => {
                document.getElementById('async-content').style.display = 'block';
            }, 1000);
        </script>
    </body>
    </html>
    """

    # Navigate to the test page

    encoded = base64.b64encode(html_content.encode()).decode()
    tab = await browser.navigate(f"data:text/html;base64,{encoded}")

    print("=" * 60)
    print("Example 1: Single element selection")
    print("=" * 60 + "\n")

    # Select single element by ID
    title = await tab.wait_for_elem("#main-title")
    if title:
        text = await title.text()
        print(f"Title text: {text.strip()}")

        # Get attribute
        test_attr = await title.attribute("data-test")
        print(f"Title data-test attribute: {test_attr}")

        # Get HTML
        html = await title.html()
        print(f"Title HTML: {html[:60]}...")

    print("\n" + "=" * 60)
    print("Example 2: Multiple element selection")
    print("=" * 60 + "\n")

    # Select all items
    items = await tab.find_elems(".item")
    print(f"Found {len(items)} items\n")

    # Process each item using direct selectors to avoid node ID invalidation
    for i in range(1, 4):  # We know we have 3 items
        print(f"Item {i} (data-id={i}):")

        # Use specific selectors for each item
        h2 = await tab.find_elem(f'.item[data-id="{i}"] h2')
        if h2:
            h2_text = await h2.text()
            print(f"  Heading: {h2_text.strip()}")

        desc = await tab.find_elem(f'.item[data-id="{i}"] .description')
        if desc:
            desc_text = await desc.text()
            print(f"  Description: {desc_text.strip()}")

        link = await tab.find_elem(f'.item[data-id="{i}"] .link')
        if link:
            href = await link.attribute("href")
            link_text = await link.text()
            print(f"  Link: {link_text.strip()} -> {href}")

        print()

    print("=" * 60)
    print("Example 3: Selecting all matching elements")
    print("=" * 60 + "\n")

    # Select all features and extract data immediately
    features = await tab.find_elems(".feature")
    print(f"Found {len(features)} features:")

    # Get all data from elements immediately before node IDs become stale
    # Note: CDP node IDs can be invalidated by subsequent DOM operations,
    # so it's best to extract all needed data in one go
    feature_data = []
    for feature in features:
        text = await feature.text()
        class_attr = await feature.attribute("class")
        feature_data.append((text, class_attr))

    # Now print the collected data
    for text, class_attr in feature_data:
        is_highlighted = "highlight" in (class_attr or "")
        marker = "[*]" if is_highlighted else "   "
        print(f"{marker} {text.strip()}")

    print("\n" + "=" * 60)
    print("Example 4: Waiting for dynamic content")
    print("=" * 60 + "\n")

    print("Waiting for #async-content to appear...")
    async_elem = await tab.wait_for_elem("#async-content", timeout=3.0)

    if async_elem:
        print("Element appeared!")
        text = await async_elem.text()
        print(f"Content: {text.strip()}")
    else:
        print("✗ Element did not appear within timeout")

    print("\n" + "=" * 60)
    print("Example 5: Complex selectors")
    print("=" * 60 + "\n")

    # Select highlighted feature specifically
    highlighted = await tab.find_elem(".feature.highlight")
    if highlighted:
        text = await highlighted.text()
        print(f"Highlighted feature: {text.strip()}")

    # Select all links within items
    all_links = await tab.find_elems(".item .link")
    print(f"\nFound {len(all_links)} links in items:")
    for link in all_links:
        href = await link.attribute("href")
        print(f"  {href}")

    # Select first item's description specifically
    first_desc = await tab.find_elem(".item:first-child .description")
    if first_desc:
        text = await first_desc.text()
        print(f"\nFirst item description: {text.strip()}")

    print("\n" + "=" * 60)
    print("Example 6: Attribute extraction")
    print("=" * 60 + "\n")

    # Get all links and their attributes
    links = await tab.find_elems("a.link")
    print("All links with attributes:")

    # Extract all data immediately to avoid node ID invalidation
    link_data = []
    for link in links:
        href = await link.attribute("href")
        class_attr = await link.attribute("class")
        text = await link.text()
        link_data.append((text, href, class_attr))

    # Now display the collected data
    for text, href, class_attr in link_data:
        print(f"  Text: {text.strip()}")
        print(f"    href: {href}")
        print(f"    class: {class_attr}")
        print()

    print("=" * 60)
    print("Example 7: Non-existent selectors")
    print("=" * 60 + "\n")

    # Try to select something that doesn't exist
    nonexistent = await tab.find_elem(".does-not-exist")
    print(f"Non-existent selector result: {nonexistent}")

    # Try to wait for something that won't appear
    print("Waiting for non-existent element (0.5s timeout)...")
    result = await tab.wait_for_elem(".never-appears", timeout=0.5)
    print(f"Result: {result}")

    # Clean up
    await browser.close()
    print("\nBrowser closed")


if __name__ == "__main__":
    asyncio.run(main())
