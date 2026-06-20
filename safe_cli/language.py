"""Language detection — warns when a file is in an unsupported language."""

from pathlib import Path
from typing import Optional

# Languages the anonymization engine covers well
SUPPORTED = {"en", "nb", "no", "nn"}

# How much text to sample for detection (more = more accurate, but slower)
_SAMPLE_CHARS = 3000


def _extract_sample(path: Path, suffix: str) -> str:
    """Extract a plain-text sample from the file for language detection."""
    try:
        if suffix in (".txt", ".csv"):
            return path.read_text(encoding="utf-8-sig", errors="replace")[:_SAMPLE_CHARS]

        if suffix == ".pdf":
            import fitz
            doc = fitz.open(str(path))
            text = doc[0].get_text() if len(doc) > 0 else ""
            doc.close()
            return text[:_SAMPLE_CHARS]

        if suffix == ".docx":
            from docx import Document
            doc = Document(str(path))
            return " ".join(p.text for p in doc.paragraphs[:30])[:_SAMPLE_CHARS]

        if suffix == ".xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            parts = []
            for sheet in list(wb.worksheets)[:1]:
                for row in sheet.iter_rows(max_row=30, values_only=True):
                    parts.extend(str(c) for c in row if isinstance(c, str))
            wb.close()
            return " ".join(parts)[:_SAMPLE_CHARS]

        if suffix == ".pptx":
            from pptx import Presentation
            prs = Presentation(str(path))
            parts = []
            for slide in list(prs.slides)[:5]:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        parts.append(shape.text_frame.text)
            return " ".join(parts)[:_SAMPLE_CHARS]

    except Exception:
        pass
    return ""


def detect(path: Path, suffix: str) -> Optional[str]:
    """
    Detect the dominant language of a file.
    Returns an ISO 639-1 code (e.g. 'nb', 'en', 'de') or None if uncertain.
    """
    try:
        from langdetect import detect_langs, DetectorFactory, LangDetectException
        DetectorFactory.seed = 0  # reproducible results

        sample = _extract_sample(path, suffix)
        if len(sample.strip()) < 30:
            return None

        langs = detect_langs(sample)
        if langs and langs[0].prob >= 0.70:
            return langs[0].lang
        return None

    except Exception:
        return None


def is_supported(lang: Optional[str]) -> bool:
    """Return True if the language is fully covered by the engine."""
    return lang is None or lang in SUPPORTED
