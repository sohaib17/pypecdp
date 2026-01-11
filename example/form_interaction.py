"""Example: Form interaction and login simulation with element manipulation.

Demonstrates form automation techniques:
- Tab.find_elem() for finding form input elements
- Elem.set_value() for filling input fields directly
- Elem.click() for clicking buttons and radio/checkboxes
- Elem.type() for keyboard input simulation that mimics typing
"""

import asyncio
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

    # Navigate to httpbin form demo
    tab = await browser.navigate("https://httpbin.org/forms/post")

    print("Filling out form...")

    # Fill customer name field
    name_field = await tab.find_elem('input[name="custname"]')
    if name_field:
        await name_field.set_value("John Doe")
        print("Name field filled")

    # Fill telephone field
    tel_field = await tab.find_elem('input[name="custtel"]')
    if tel_field:
        await tel_field.set_value("555-1234")
        print("Telephone field filled")

    # Fill email field using type() method
    email_field = await tab.find_elem('input[name="custemail"]')
    if email_field:
        await email_field.click()  # Focus the field first
        await email_field.type("john.doe@example.com")
        print("Email field typed")

    # Select pizza size (medium)
    medium_radio = await tab.find_elem('input[value="medium"]')
    if medium_radio:
        await medium_radio.click()
        print("Pizza size selected")

    # Select toppings using checkboxes
    toppings = ["bacon", "cheese"]
    for topping in toppings:
        checkbox = await tab.find_elem(f'input[value="{topping}"]')
        if checkbox:
            await checkbox.click()
            print(f"{topping.capitalize()} topping selected")

    # Fill delivery time
    time_field = await tab.find_elem('input[name="delivery"]')
    if time_field:
        await time_field.set_value("12:30")
        print("Delivery time set")

    # Fill comments textarea
    comments = await tab.find_elem('textarea[name="comments"]')
    if comments:
        await comments.set_value("Please ring the doorbell twice!")
        print("Comments added")

    print("\nForm filled successfully!")
    print("In real automation, you would now submit the form with:")
    print("  submit_btn = await tab.find_elem('button[type=\"submit\"]')")
    print("  await submit_btn.click()")

    # Wait a moment to see the filled form
    await asyncio.sleep(1)

    # Clean up
    await browser.close()
    print("\nBrowser closed")


if __name__ == "__main__":
    asyncio.run(main())
