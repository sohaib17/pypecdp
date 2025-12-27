"""Example: Custom event handlers for Target lifecycle events.

Demonstrates event handling and monitoring for browser targets:
- Registering event handlers with Browser.on() for browser-level events
- Target.targetCreated and Target.targetDestroyed events
- Target.attachedToTarget and Target.detachedFromTarget events
- Tracking tab lifecycle in real-time
- Custom event handlers for monitoring target state changes
"""

import asyncio
import os
from datetime import datetime
from typing import Any

from pypecdp import Browser, cdp


def timestamp() -> str:
    """Return current timestamp string."""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


async def main() -> None:
    """Main."""
    # Event tracking
    events_log: list[str] = []

    # Handler for target creation
    async def on_target_created(event: Any) -> None:
        # event is a TargetCreated object with target_info attribute
        info = event.target_info
        target_type = info.type_
        url = info.url

        msg = f"[{timestamp()}] Target created: {target_type} | {url[:50]}"
        events_log.append(msg)
        print(msg)

    # Handler for target destruction
    async def on_target_destroyed(event: Any) -> None:
        # event is a TargetDestroyed object with target_id attribute
        target_id = str(event.target_id)

        msg = f"[{timestamp()}] Target destroyed: {target_id[:20]}..."
        events_log.append(msg)
        print(msg)

    # Handler for target attachment
    async def on_attached(event: Any) -> None:
        # event is an AttachedToTarget object with session_id and target_info attributes
        session_id = str(event.session_id)
        target_id = str(event.target_info.target_id)

        msg = f"[{timestamp()}] Attached to target: {target_id[:20]}... (session: {session_id[:20]}...)"
        events_log.append(msg)
        print(msg)

    # Handler for target detachment
    async def on_detached(event: Any) -> None:
        # event is a DetachedFromTarget object with session_id attribute
        session_id = str(event.session_id)

        msg = f"[{timestamp()}] Detached from session: {session_id[:20]}..."
        events_log.append(msg)
        print(msg)

    # Handler for target info changes
    async def on_target_info_changed(event: Any) -> None:
        # event is a TargetInfoChanged object with target_info attribute
        info = event.target_info
        target_id = str(info.target_id)
        url = info.url

        msg = f"[{timestamp()}] Target info changed: {target_id[:20]}... | {url[:50]}"
        events_log.append(msg)
        print(msg)

    print("=" * 60)
    print("Starting browser with event monitoring...")
    print("=" * 60 + "\n")

    # Start browser and register event handlers
    browser = await Browser.start(
        chrome_path=os.environ.get("PYPECDP_CHROME_PATH", "chromium"),
        headless=True,
        extra_args=["--no-sandbox"],
    )

    # Register all handlers after browser is created
    browser.on(cdp.target.TargetCreated, on_target_created)
    browser.on(cdp.target.TargetDestroyed, on_target_destroyed)
    browser.on(cdp.target.AttachedToTarget, on_attached)
    browser.on(cdp.target.DetachedFromTarget, on_detached)
    browser.on(cdp.target.TargetInfoChanged, on_target_info_changed)

    await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print("Creating tabs...")
    print("=" * 60 + "\n")

    # Create first tab
    tab1 = await browser.navigate("https://example.com", new_tab=True)
    await asyncio.sleep(0.5)

    # Create second tab
    _ = await browser.navigate("https://example.org", new_tab=True)
    await asyncio.sleep(0.5)

    # Navigate first tab to a different URL (triggers targetInfoChanged)
    print("\n" + "=" * 60)
    print("Navigating tab1 to new URL...")
    print("=" * 60 + "\n")

    await tab1.navigate("https://www.iana.org/domains/reserved")
    await asyncio.sleep(0.5)

    # Close first tab (triggers targetDestroyed and detached)
    print("\n" + "=" * 60)
    print("Closing tab1...")
    print("=" * 60 + "\n")

    await tab1.close()
    await asyncio.sleep(0.5)

    # Create a new tab after closing one
    print("\n" + "=" * 60)
    print("Creating tab3...")
    print("=" * 60 + "\n")

    _ = await browser.navigate("https://httpbin.org/html", new_tab=True)
    await asyncio.sleep(0.5)

    # Example with multiple event handlers on same event
    print("\n" + "=" * 60)
    print("Adding second handler for targetCreated...")
    print("=" * 60 + "\n")

    async def second_target_created_handler(event: Any) -> None:
        # event is a TargetCreated object with target_info attribute
        target_type = event.target_info.type_
        print(f"  [Secondary handler] Detected {target_type} target")

    browser.on(cdp.target.TargetCreated, second_target_created_handler)

    # Create another tab - both handlers will fire
    _ = await browser.navigate("about:blank", new_tab=True)
    await asyncio.sleep(0.5)

    # Summary
    print("\n" + "=" * 60)
    print("Event Summary")
    print("=" * 60)
    print(f"Total events captured: {len(events_log)}\n")

    # Count events by type
    event_types: dict[str, int] = {}
    for log in events_log:
        if "created" in log:
            event_types["created"] = event_types.get("created", 0) + 1
        elif "destroyed" in log:
            event_types["destroyed"] = event_types.get("destroyed", 0) + 1
        elif "Attached" in log:
            event_types["attached"] = event_types.get("attached", 0) + 1
        elif "Detached" in log:
            event_types["detached"] = event_types.get("detached", 0) + 1
        elif "changed" in log:
            event_types["info_changed"] = (
                event_types.get("info_changed", 0) + 1
            )

    print("Event breakdown:")
    for event_type, count in sorted(event_types.items()):
        print(f"  {event_type}: {count}")

    print(f"\nCurrent targets in browser: {len(browser.targets)}")

    # Clean up
    print("\n" + "=" * 60)
    print("Closing browser...")
    print("=" * 60 + "\n")

    await browser.close()

    print("\nBrowser closed")
    print(f"Total events logged: {len(events_log)}")


if __name__ == "__main__":
    asyncio.run(main())
