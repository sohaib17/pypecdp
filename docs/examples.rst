Examples
========

This page provides code snippets demonstrating common pypecdp usage patterns.

For complete, runnable examples, see the `example/ directory <https://github.com/sohaib17/pypecdp/tree/main/example>`_ in the GitHub repository.

Basic Usage
-----------

Navigate and Extract Text
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from pypecdp import Browser

   async def main():
       browser = await Browser.start(headless=True)
       tab = await browser.navigate("https://example.com")

       h1 = await tab.wait_for_elem("h1")
       print(await h1.text())

       await browser.close()

   asyncio.run(main())

Click Elements
~~~~~~~~~~~~~~

.. code-block:: python

   async def click_example():
       browser = await Browser.start()
       tab = await browser.navigate("https://example.com")

       button = await tab.find_elem("button.submit")
       current_tab = await button.click()  # Returns root Tab if click happened

       await browser.close()

Form Filling and Submission
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   async def form_example():
       browser = await Browser.start()
       tab = await browser.navigate("https://example.com/login")

       # Fill in form fields
       username = await tab.wait_for_elem("input[name='username']")
       await username.type("myuser")

       password = await tab.wait_for_elem("input[name='password']")
       await password.type("mypassword")

       # Submit form
       submit_btn = await tab.find_elem("button[type='submit']")
       await submit_btn.click()

       await browser.close()

JavaScript Evaluation
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   async def eval_example():
       browser = await Browser.start()
       tab = await browser.navigate("https://example.com")

       # Get page title
       result = await tab.eval("document.title")
       print(f"Title: {result.value}")

       # Get multiple values
       result = await tab.eval("""
           ({
               url: window.location.href,
               width: window.innerWidth,
               height: window.innerHeight
           })
       """)
       print(f"Page info: {result.value}")

       await browser.close()

Taking Screenshots
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pypecdp import cdp
   import base64

   async def screenshot_example():
       browser = await Browser.start(headless=True)
       tab = await browser.navigate("https://example.com")

       # Wait for page to load
       await tab.wait_for_event(cdp.page.LoadEventFired, timeout=10.0)

       # Capture screenshot
       result = await tab.send(cdp.page.CaptureScreenshot(format_="png"))
       screenshot_data = base64.b64decode(result.data)

       # Save to file
       with open("screenshot.png", "wb") as f:
           f.write(screenshot_data)

       await browser.close()

Working with Multiple Elements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   async def multiple_elements_example():
       browser = await Browser.start()
       tab = await browser.navigate("https://example.com")

       # Find all links on the page
       links = await tab.wait_for_elems("a", timeout=5.0)
       
       for link in links:
           href = await link.get_attr("href")
           text = await link.text()
           print(f"{text}: {href}")

       await browser.close()

Event Handling
~~~~~~~~~~~~~~

.. code-block:: python

   from pypecdp import cdp

   async def event_example():
       browser = await Browser.start()
       tab = await browser.navigate("https://example.com")

       # Enable console events
       await tab.send(cdp.runtime.enable())

       # Register event handler
       async def on_console(event):
           print(f"Console {event.type_}: {event.args}")

       tab.on(cdp.runtime.ConsoleAPICalled, on_console)

       # Trigger console output
       await tab.eval("console.log('Hello from browser!')")

       await browser.close()

Profile Management
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   async def profile_example():
       # Preserve browser state between runs
       browser = await Browser.start(
           headless=False,
           user_data_dir="/tmp/my-profile",
           clean_data_dir=False  # Don't delete on close
       )

       tab = await browser.navigate("https://example.com")
       # Login, set cookies, etc.

       await browser.close()

       # Next run uses same profile
       browser = await Browser.start(
           user_data_dir="/tmp/my-profile",
           clean_data_dir=False
       )
       # Still logged in!

Low-Level CDP
~~~~~~~~~~~~~

.. code-block:: python

   from pypecdp import cdp

   async def cdp_example():
       browser = await Browser.start()
       tab = await browser.navigate("https://example.com")

       # Send raw CDP commands
       result = await tab.send(cdp.runtime.Evaluate(
           expression="document.title",
           returnByValue=True
       ))
       print(result.result.value)

       # Wait for CDP events
       event = await tab.wait_for_event(
           cdp.page.LoadEventFired,
           timeout=10.0
       )

       await browser.close()

