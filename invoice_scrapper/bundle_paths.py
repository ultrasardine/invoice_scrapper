"""Resolve paths for bundled resources (Tesseract) in packaged apps."""

import os
import sys
from pathlib import Path


def _get_bundle_dir() -> Path:
    """Get the base directory for bundled resources.

    When packaged with PyInstaller, sys._MEIPASS points to the temp
    extraction directory. Otherwise, use the project root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent


def configure_tesseract() -> None:
    """Set Tesseract binary and tessdata paths for packaged apps."""
    if not getattr(sys, "frozen", False):
        return  # Running from source — use system Tesseract

    bundle = _get_bundle_dir()

    # Set Tesseract binary path
    if sys.platform == "win32":
        tess_bin = bundle / "tesseract.exe"
    else:
        tess_bin = bundle / "tesseract"

    if tess_bin.exists():
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = str(tess_bin)

    # Set tessdata directory
    tessdata = bundle / "tessdata"
    if tessdata.exists():
        os.environ["TESSDATA_PREFIX"] = str(tessdata)
