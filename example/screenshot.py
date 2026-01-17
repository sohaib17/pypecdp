"""Example: Screenshot capture using CDP Page.captureScreenshot.

Demonstrates capturing screenshots programmatically:
- Using cdp.page.capture_screenshot() command
- Base64 decoding and saving PNG data to file
- Full page screenshots by adjusting viewport
- Viewport screenshots with custom dimensions
- Element-specific screenshots using clip regions
"""

import asyncio
import base64
import os
import tempfile
from pathlib import Path

from pypecdp import Browser, cdp


async def main() -> None:
    """Main."""
    temp_dir = tempfile.gettempdir()
    # Launch browser
    browser = await Browser.start(
        chrome_path=os.environ.get("PYPECDP_CHROME_PATH", "chromium"),
        headless=True,
        extra_args=["--no-sandbox"],
    )

    # Navigate to a page
    tab = await browser.navigate("https://example.com")
    print("Page loaded: https://example.com")

    # Wait for page to fully render
    await asyncio.sleep(1)

    # Capture viewport screenshot (default)
    print("\n1. Capturing viewport screenshot...")
    data = await tab.send(
        cdp.page.capture_screenshot(format_="jpeg", quality=90)
    )

    # Decode base64 and save
    img_data = base64.b64decode(data)
    output_path = Path(temp_dir, "example_viewport.png")
    output_path.write_bytes(img_data)
    print(f"Saved to {output_path} ({len(img_data)} bytes)")

    # Capture full page screenshot
    print("\n2. Capturing full page screenshot...")

    # Get document dimensions
    metrics = await tab.send(cdp.page.get_layout_metrics())
    content_size = metrics[5]  # contentSize

    # Set viewport to full content size
    await tab.send(
        cdp.emulation.set_device_metrics_override(
            width=int(content_size.width),
            height=int(content_size.height),
            device_scale_factor=1,
            mobile=False,
        )
    )

    # Capture full page
    data = await tab.send(cdp.page.capture_screenshot(format_="png"))

    img_data = base64.b64decode(data)
    output_path = Path(temp_dir, "example_fullpage.png")
    output_path.write_bytes(img_data)
    print(f"Saved to {output_path} ({len(img_data)} bytes)")

    # Capture screenshot of specific element
    print("\n3. Capturing element screenshot...")

    # Find h1 element
    h1 = await tab.find_elem("h1")
    if h1:
        # Get element's bounding box
        box_model = await tab.send(
            cdp.dom.get_box_model(backend_node_id=h1.backend_node_id)
        )
        content = box_model.content  # content quad

        # Calculate viewport clip (x, y, width, height)
        x = min(content[0], content[2], content[4], content[6])
        y = min(content[1], content[3], content[5], content[7])
        max_x = max(content[0], content[2], content[4], content[6])
        max_y = max(content[1], content[3], content[5], content[7])
        width = max_x - x
        height = max_y - y

        # Capture with clip
        data = await tab.send(
            cdp.page.capture_screenshot(
                format_="png",
                clip=cdp.page.Viewport(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    scale=1.0,
                ),
            )
        )

        img_data = base64.b64decode(data)
        output_path = Path(temp_dir, "example_element.png")
        output_path.write_bytes(img_data)
        print(f"Saved to {output_path} ({len(img_data)} bytes)")

    # Clean up
    await browser.close()
    print("\nBrowser closed")
    print("\nScreenshots saved:")
    print("  - example_viewport.png (viewport)")
    print("  - example_fullpage.png (full page)")
    print("  - example_element.png (h1 element)")


if __name__ == "__main__":
    asyncio.run(main())
