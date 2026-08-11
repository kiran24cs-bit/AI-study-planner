"""OCR helper for image uploads (timetables / syllabus photos).

Requires the Tesseract binary to be installed on the host machine.
If it is missing we return an empty string so the caller can fall back to
manual entry instead of crashing.
"""


def image_to_text(path: str) -> str:
    """Run OCR on an image file. Returns '' when OCR is unavailable."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    try:
        with Image.open(path) as image:
            # Grayscale improves OCR accuracy on scanned documents.
            return pytesseract.image_to_string(image.convert("L"))
    except Exception:
        return ""


def extract_text_from_upload(path: str) -> str:
    """Dispatch to the right extractor based on file extension."""
    lowered = path.lower()
    if lowered.endswith(".pdf"):
        from utils.pdf_parser import extract_text

        return extract_text(path)
    return image_to_text(path)
