"""Invoice Scrapper - Desktop app entry point."""

from invoice_scrapper.bundle_paths import configure_tesseract

configure_tesseract()

import flet as ft

from invoice_scrapper.ui.app import main


if __name__ == "__main__":
    ft.run(main)
