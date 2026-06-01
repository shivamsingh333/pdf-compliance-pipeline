"""
PDF Text Extraction Utility
Uses PyMuPDF (fitz) to extract text page-by-page with encoding detection.
"""
import io
import chardet

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


def extract_text_by_page(uploaded_file) -> list[dict]:
    """
    Extract text from each page of a PDF.
    Returns a list of dicts: [{page_num, text, word_count, encoding_issues}]
    """
    file_bytes = uploaded_file.read()
    uploaded_file.seek(0)

    pages = []

    if PYMUPDF_AVAILABLE:
        pages = _extract_with_pymupdf(file_bytes)
    elif PDFPLUMBER_AVAILABLE:
        pages = _extract_with_pdfplumber(file_bytes)
    else:
        raise ImportError(
            "No PDF library found. Install with: pip install pymupdf pdfplumber"
        )

    return pages


def _extract_with_pymupdf(file_bytes: bytes) -> list[dict]:
    """Extract using PyMuPDF — best quality, preserves structure."""
    import fitz
    pages = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        # Detect encoding issues
        encoding_issues = _check_encoding(text)

        pages.append({
            "page_num": page_num + 1,
            "text": text,
            "word_count": len(text.split()),
            "char_count": len(text),
            "encoding_issues": encoding_issues,
            "has_text": len(text.strip()) > 0
        })

    doc.close()
    return pages


def _extract_with_pdfplumber(file_bytes: bytes) -> list[dict]:
    """Fallback extraction using pdfplumber."""
    import pdfplumber
    pages = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            encoding_issues = _check_encoding(text)

            pages.append({
                "page_num": page_num + 1,
                "text": text,
                "word_count": len(text.split()),
                "char_count": len(text),
                "encoding_issues": encoding_issues,
                "has_text": len(text.strip()) > 0
            })

    return pages


def _check_encoding(text: str) -> list[str]:
    """Check for potential encoding inconsistencies in text."""
    issues = []
    if not text:
        return issues

    # Check for common encoding artifacts
    encoding_artifacts = [
        "\ufffd",  # replacement character
        "\x00",    # null bytes
        "\x1a",    # SUB character
    ]
    for artifact in encoding_artifacts:
        if artifact in text:
            issues.append(f"Contains character: {repr(artifact)}")

    # Check for non-ASCII characters (may indicate non-UTF8 content)
    non_ascii = [c for c in text if ord(c) > 127 and not c.isprintable()]
    if non_ascii:
        issues.append(f"{len(non_ascii)} non-printable non-ASCII characters found")

    # Check for mixed scripts (basic detection)
    has_latin = any('\u0041' <= c <= '\u007A' for c in text)
    has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in text)
    has_arabic = any('\u0600' <= c <= '\u06FF' for c in text)
    has_cjk = any('\u4E00' <= c <= '\u9FFF' for c in text)

    non_latin_scripts = sum([has_cyrillic, has_arabic, has_cjk])
    if has_latin and non_latin_scripts > 0:
        issues.append("Mixed scripts detected — possible non-English content")

    return issues


def get_full_text(pages: list[dict]) -> str:
    """Concatenate all pages into a single string."""
    return "\n\n--- Page Break ---\n\n".join(
        f"[PAGE {p['page_num']}]\n{p['text']}"
        for p in pages
        if p['has_text']
    )