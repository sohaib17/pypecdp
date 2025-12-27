---
name: Bug report
about: Create a report to help us improve
title: "[BUG] "
labels: ''
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Add a minimal working code snippet here:
```
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
```

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Desktop (please complete the following information):**
 - OS: [e.g. Ubuntu 24.04]
 - Chrome/Chromium version: [e.g. 142.0.7444.175]
 - PypeCDP version [e.g. 0.3.0]

**Additional context**
Add any other context about the problem here.
