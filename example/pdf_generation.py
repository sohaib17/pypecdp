"""Example: PDF generation using CDP Page.printToPDF.

Demonstrates generating PDF files from web pages:
- Using cdp.page.print_to_pdf() command
- Base64 decoding and saving PDF data to file
- Custom page sizes and margins
- Landscape orientation
- Header and footer templates with page numbers
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
    # Launch browser (headless required for PDF)
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

    # Generate basic PDF
    print("\n1. Generating basic PDF...")
    data, _ = await tab.send(
        cdp.page.print_to_pdf(
            print_background=True,
            prefer_css_page_size=False,
        )
    )

    # Decode base64 and save
    pdf_data = base64.b64decode(data)
    output_path = Path(temp_dir, "example_basic.pdf")
    output_path.write_bytes(pdf_data)
    print(f"Saved to {output_path} ({len(pdf_data)} bytes)")

    # Generate PDF with custom settings
    print("\n2. Generating PDF with custom settings...")
    data, _ = await tab.send(
        cdp.page.print_to_pdf(
            landscape=True,  # Landscape orientation
            print_background=True,
            scale=0.8,  # 80% scale
            paper_width=11.0,  # Letter width in inches
            paper_height=8.5,  # Letter height in inches (landscape)
            margin_top=0.5,  # 0.5 inch margins
            margin_bottom=0.5,
            margin_left=0.5,
            margin_right=0.5,
            page_ranges="",  # All pages
        )
    )

    pdf_data = base64.b64decode(data)
    output_path = Path(temp_dir, "example_custom.pdf")
    output_path.write_bytes(pdf_data)
    print(f"Saved to {output_path} ({len(pdf_data)} bytes)")

    # Generate PDF with header and footer
    print("\n3. Generating PDF with header/footer...")
    data, _ = await tab.send(
        cdp.page.print_to_pdf(
            display_header_footer=True,
            header_template="""
                <div style="font-size:10px; text-align:center; width:100%;">
                    <span class="title"></span>
                </div>
            """,
            footer_template="""
                <div style="font-size:10px; text-align:center; width:100%;">
                    Page <span class="pageNumber"></span> of <span class="totalPages"></span>
                </div>
            """,
            print_background=True,
            margin_top=1.0,  # Larger top margin for header
            margin_bottom=1.0,  # Larger bottom margin for footer
        )
    )

    pdf_data = base64.b64decode(data)
    output_path = Path(temp_dir, "example_header_footer.pdf")
    output_path.write_bytes(pdf_data)
    print(f"Saved to {output_path} ({len(pdf_data)} bytes)")

    # Navigate to a longer page and generate multi-page PDF
    print("\n4. Generating multi-page PDF...")
    await tab.navigate("https://www.example.org")
    await asyncio.sleep(1)

    data, _ = await tab.send(
        cdp.page.print_to_pdf(
            print_background=True,
            prefer_css_page_size=False,
            paper_width=8.5,  # US Letter
            paper_height=11.0,
        )
    )

    pdf_data = base64.b64decode(data)
    output_path = Path(temp_dir, "example_multipage.pdf")
    output_path.write_bytes(pdf_data)
    print(f"Saved to {output_path} ({len(pdf_data)} bytes)")

    # Clean up
    await browser.close()
    print("\nBrowser closed")
    print("\nPDFs generated:")
    print("  - example_basic.pdf")
    print("  - example_custom.pdf (landscape, custom margins)")
    print("  - example_header_footer.pdf (with page numbers)")
    print("  - example_multipage.pdf")


if __name__ == "__main__":
    asyncio.run(main())
