from pathlib import Path
from typing import Dict

import fitz  # PyMuPDF

from ..engine import AnonymizerCore, ENTITY_TO_PLACEHOLDER
from ..media import PLACEHOLDER_IMAGE, PLACEHOLDER_VIDEO, PLACEHOLDER_AUDIO

# PDF annotation type names that indicate multimedia content
_MULTIMEDIA_ANNOT_TYPES = {"Screen", "Sound", "Movie", "RichMedia"}


def _redact_images(page, stats: Dict[str, int]) -> None:
    """Cover every image on the page with a grey placeholder box."""
    for img_info in page.get_image_info():
        rect = fitz.Rect(img_info["bbox"])
        if rect.is_empty or rect.is_infinite:
            continue
        page.add_redact_annot(
            rect,
            text=PLACEHOLDER_IMAGE,
            fontsize=6,
            fill=(0.85, 0.85, 0.85),  # light grey
            text_color=(0, 0, 0),
        )
        stats[PLACEHOLDER_IMAGE] = stats.get(PLACEHOLDER_IMAGE, 0) + 1


def _remove_multimedia_annotations(page, stats: Dict[str, int]) -> None:
    """Delete Screen/Sound/Movie/RichMedia annotations (embedded video & audio)."""
    for annot in list(page.annots()):
        type_name = annot.type[1] if len(annot.type) > 1 else ""
        if type_name in _MULTIMEDIA_ANNOT_TYPES:
            if type_name == "Sound":
                label = PLACEHOLDER_AUDIO
            else:
                label = PLACEHOLDER_VIDEO
            stats[label] = stats.get(label, 0) + 1
            page.delete_annot(annot)


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    stats: Dict[str, int] = {}

    try:
        doc = fitz.open(str(input_path))
    except Exception as exc:
        raise RuntimeError(f"Cannot open PDF: {exc}") from exc

    if doc.needs_pass:
        doc.close()
        raise RuntimeError("PDF is password-protected; cannot anonymize.")

    for page in doc:
        # 1. Redact embedded images and multimedia annotations
        _redact_images(page, stats)
        _remove_multimedia_annotations(page, stats)

        # 2. Redact PII in text — apply with image pixel removal so redacted
        #    image areas are fully cleared (not just annotated)
        text = page.get_text()
        if text.strip():
            results = engine.analyze(text)
            for result in results:
                placeholder = ENTITY_TO_PLACEHOLDER.get(result.entity_type, "[SENSITIVE_DATA]")
                stats[placeholder] = stats.get(placeholder, 0) + 1

                entity_text = text[result.start : result.end].strip()
                if not entity_text:
                    continue

                for rect in page.search_for(entity_text):
                    chars = max(len(placeholder), 1)
                    fontsize = max(4.0, min(rect.width / (chars * 0.6), 7.0))
                    page.add_redact_annot(
                        rect,
                        text=placeholder,
                        fontsize=fontsize,
                        fill=(1, 1, 1),
                        text_color=(0, 0, 0),
                    )

        # Apply all redactions; remove pixels under image redaction areas
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)

    doc.save(str(output_path))
    doc.close()
    return stats
