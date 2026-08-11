"""PDF text extraction with a graceful fallback chain.

pdfplumber gives the best layout fidelity; PyPDF2 is the fallback when
pdfplumber cannot open the file.
"""


def extract_text(path: str) -> str:
    """Return all text found in a PDF, or an empty string on failure."""
    text = _try_pdfplumber(path)
    if text.strip():
        return text
    return _try_pypdf2(path)


def _try_pdfplumber(path: str) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""

    chunks = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                chunks.append(page.extract_text() or "")
                # Tables often hold the exam timetable grid.
                for table in page.extract_tables() or []:
                    for row in table:
                        cells = [c for c in row if c]
                        if cells:
                            chunks.append(" | ".join(cells))
    except Exception:
        return ""
    return "\n".join(chunks)


def _try_pypdf2(path: str) -> str:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""
