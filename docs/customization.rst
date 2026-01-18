Customization
=============

pypecdp supports customization through standard OOP inheritance. You can extend the ``Browser``, ``Tab``, and ``Elem`` classes to add your own methods or override existing behavior.

How It Works
------------

Each class has a class attribute that specifies which class to use for child instances:

* ``Browser.tab_class`` - Class to use when creating Tab instances
* ``Tab.elem_class`` - Class to use when creating Elem instances

By default, these are set to ``Tab`` and ``Elem`` respectively, but you can override them in your custom classes.

Basic Example
-------------

.. code-block:: python

   from pypecdp import Browser, Tab, Elem, cdp

   class MyElem(Elem):
       """Custom element with additional methods."""

       async def click_and_wait(self, timeout=10.0):
           """Click element and wait for page load."""
           tab = await self.click()
           if tab:
               await tab.wait_for_event(cdp.page.LoadEventFired, timeout=timeout)

   class MyTab(Tab):
       """Custom tab that uses MyElem."""
       elem_class = MyElem  # Use custom Elem class

       async def get_title(self):
           """Get page title."""
           result = await self.eval("document.title")
           return result.value

   class MyBrowser(Browser):
       """Custom browser that uses MyTab."""
       tab_class = MyTab  # Use custom Tab class

Usage
-----

Once you've defined your custom classes, use them like the standard classes:

.. code-block:: python

   import asyncio

   async def main():
       # Create browser with custom classes
       browser = await MyBrowser.start()

       # navigate() returns MyTab instance
       tab = await browser.navigate("https://example.com")

       # Custom method from MyTab
       title = await tab.get_title()
       print(f"Title: {title}")

       # find_elem() returns MyElem instance
       button = await tab.find_elem("button")

       # Custom method from MyElem
       await button.click_and_wait()

       await browser.close()

   asyncio.run(main())

Use Cases
---------

Domain-Specific Automation
~~~~~~~~~~~~~~~~~~~~~~~~~~

Add methods specific to your application:

.. code-block:: python

   class EcommerceTab(Tab):
       async def add_to_cart(self, product_id):
           button = await self.find_elem(f"button[data-product='{product_id}']")
           await button.click()
           await self.wait_for_elem(".cart-count")

Logging and Monitoring
~~~~~~~~~~~~~~~~~~~~~~

Wrap methods with logging:

.. code-block:: python

   class LoggingTab(Tab):
       async def navigate(self, url):
           print(f"Navigating to: {url}")
           result = await super().navigate(url)
           print(f"Navigation complete")
           return result

Retry Logic
~~~~~~~~~~~

Add automatic retries:

.. code-block:: python

   class RetryElem(Elem):
       async def click(self, retries=3):
           for attempt in range(retries):
               try:
                   return await super().click()
               except Exception as e:
                   if attempt == retries - 1:
                       raise
                   await asyncio.sleep(1)

Best Practices
--------------

1. **Set class attributes** - Don't forget to set ``tab_class`` and ``elem_class`` to propagate your custom classes through the hierarchy.

2. **Call super()** - When overriding methods, call ``super()`` to preserve base functionality.

3. **Keep it focused** - Create specific custom classes for different use cases rather than one monolithic class.

4. **Type hints** - Use proper type hints for better IDE support:

   .. code-block:: python

      class MyBrowser(Browser):
          tab_class: type[MyTab] = MyTab  # Explicit type hint

Complete Example
----------------

See ``example/customize_pypecdp.py`` in the repository for a complete working example.
