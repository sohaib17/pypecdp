"""Example: Working with cookies in pypecdp."""

import asyncio
import os

from pypecdp import Browser


async def main() -> None:
    """Demonstrate cookie handling."""
    browser = await Browser.start(
        chrome_path=os.environ.get("PYPECDP_CHROME_PATH", "chromium"),
        headless=True,
    )
    # Navigate to a site that sets cookies
    await browser.navigate(
        "https://httpbin.org/cookies/set?name1=value1&name2=value2"
    )
    await asyncio.sleep(2)  # Wait for cookies to be set
    # Get all cookies as a CookieJar
    jar = await browser.cookies()
    print(f"Found {len(jar)} cookies:")
    for cookie in jar:
        print(f"  {cookie.name} = {cookie.value}")
        print(f"    Domain: {cookie.domain}")
        print(f"    Path: {cookie.path}")
        print(f"    Secure: {cookie.secure}")
        print(f"    HttpOnly: {cookie._rest.get('HttpOnly', 'False')}")
        if cookie.expires:
            print(f"    Expires: {cookie.expires}")
        print()

    await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
