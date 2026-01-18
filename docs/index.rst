pypecdp - Chrome DevTools Protocol over POSIX Pipes
===================================================

**pypecdp** is a Python library for Chrome automation using the Chrome DevTools Protocol (CDP) over POSIX pipes.

Key Features
------------

* 🚀 Direct POSIX pipe communication (no WebSockets, no ports)
* ⚡ Fully async with asyncio
* 🪶 Minimal dependencies (only ``deprecated``)
* 🔒 Secure by default (local pipes only)
* 🧹 Automatic lifecycle management
* 🥷 No bot signatures - raw CDP with user in full control

Quick Start
-----------

Installation::

   pip install pypecdp

Basic usage::

   import asyncio
   from pypecdp import Browser

   async def main():
       browser = await Browser.start(headless=True)
       tab = await browser.navigate("https://example.com")

       h1 = await tab.wait_for_elem("h1")
       print(await h1.text())

       await browser.close()

   asyncio.run(main())

Links
-----

* `GitHub Repository <https://github.com/sohaib17/pypecdp>`_
* `PyPI Package <https://pypi.org/project/pypecdp/>`_
* `Issue Tracker <https://github.com/sohaib17/pypecdp/issues>`_
* `Chrome DevTools Protocol <https://chromedevtools.github.io/devtools-protocol/>`_

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: Documentation

   api
   examples
   customization

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
