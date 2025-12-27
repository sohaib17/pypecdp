"""Example: Console logging using Runtime.consoleAPICalled events.

Demonstrates how to capture and monitor console messages from the browser:
- Subscribing to Runtime.consoleAPICalled events
- Capturing console.log, console.warn, console.error messages
- Extracting and displaying console message arguments
- Real-time console monitoring during page execution
"""

import asyncio
import base64
import os
from typing import Any

from pypecdp import Browser, cdp


async def main() -> None:
    """Main."""
    # Launch browser
    browser = await Browser.start(
        chrome_path=os.environ.get("PYPECDP_CHROME_PATH", "chromium"),
        headless=True,
        extra_args=["--no-sandbox"],
    )

    tab = await browser.navigate("about:blank")
    await tab.send(cdp.runtime.enable())
    print("Browser launched\n")

    # Storage for console messages
    console_messages: list[tuple[str, str]] = []

    # Handler for console API calls
    async def handle_console(event: Any) -> None:
        """Handle Runtime.consoleAPICalled events."""
        # event is a ConsoleAPICalled object
        msg_type = event.type_
        args = event.args

        # Extract values from arguments
        values = []
        for arg in args:
            arg_type = arg.type_
            if arg_type == "string":
                values.append(arg.value if hasattr(arg, "value") else "")
            elif arg_type == "number":
                values.append(str(arg.value if hasattr(arg, "value") else ""))
            elif arg_type == "boolean":
                values.append(str(arg.value if hasattr(arg, "value") else ""))
            elif arg_type == "object":
                desc = (
                    arg.description
                    if hasattr(arg, "description")
                    else "Object"
                )
                values.append(desc)
            else:
                values.append(f"[{arg_type}]")

        message = " ".join(values)

        # Format with prefix markers
        prefix = {
            "log": "[i]",
            "info": "[i]",
            "warn": "[!]",
            "error": "[x]",
            "debug": "[d]",
        }.get(msg_type, "[*]")

        formatted = f"{prefix} [{msg_type.upper()}] {message}"
        console_messages.append((msg_type, message))
        print(formatted)

    # Register the console handler
    tab.on(cdp.runtime.ConsoleAPICalled, handle_console)

    print("=" * 60)
    print("Capturing console messages...")
    print("=" * 60 + "\n")

    # Execute various console commands
    await tab.eval("console.log('Hello from pypecdp!')")
    await asyncio.sleep(0.1)

    await tab.eval("console.log('Multiple', 'arguments', 123)")
    await asyncio.sleep(0.1)

    await tab.eval("console.warn('This is a warning')")
    await asyncio.sleep(0.1)

    await tab.eval("console.error('This is an error')")
    await asyncio.sleep(0.1)

    await tab.eval("console.info('Info message with number:', 42)")
    await asyncio.sleep(0.1)

    await tab.eval("console.log('Boolean:', true, false)")
    await asyncio.sleep(0.1)

    await tab.eval("console.log('Object:', {foo: 'bar', num: 123})")
    await asyncio.sleep(0.1)

    await tab.eval("console.log('Array:', [1, 2, 3])")
    await asyncio.sleep(0.1)

    # Navigate to a page and capture its console output
    print("\n" + "=" * 60)
    print("Navigating to page with console output...")
    print("=" * 60 + "\n")

    # Create a page with console output
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Console Test</title></head>
    <body>
        <h1>Console Test Page</h1>
        <script>
            console.log('Page loaded!');
            console.info('Current URL:', window.location.href);
            console.warn('This is a warning from the page');
            
            setTimeout(() => {
                console.log('Delayed message after 500ms');
            }, 500);
            
            setTimeout(() => {
                console.error('Simulated error after 1000ms');
            }, 1000);
        </script>
    </body>
    </html>
    """

    # Navigate to data URL with the HTML
    encoded = base64.b64encode(html_content.encode()).decode()
    await tab.navigate(f"data:text/html;base64,{encoded}")

    # Wait for delayed messages
    await asyncio.sleep(1.5)

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total console messages captured: {len(console_messages)}")

    # Count by type
    type_counts: dict[str, int] = {}
    for msg_type, _ in console_messages:
        type_counts[msg_type] = type_counts.get(msg_type, 0) + 1

    print("\nBreakdown by type:")
    for msg_type, count in sorted(type_counts.items()):
        print(f"  {msg_type}: {count}")

    # Clean up
    await browser.close()
    print("\nBrowser closed")


if __name__ == "__main__":
    asyncio.run(main())
