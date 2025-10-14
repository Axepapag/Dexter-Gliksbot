"""
Windows OCR stubs for testing.
Will be properly implemented with Tesseract in Windows tools extraction task.
"""
from typing import Optional


def ocr_hwnd(hwnd: int, tesseract_path: Optional[str] = None) -> str:
    """Stub for OCR on window handle"""
    # In real implementation: Use Tesseract OCR
    return "Sample OCR text"
