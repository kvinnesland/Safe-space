from pathlib import Path
from typing import Dict

import fitz  # PyMuPDF

from ..engine import AnonymizerCore, ENTITY_TO_PLACEHOLDER, ENTITIES, CONFIDENCE_THRESHOLD


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
        text = page.get_text()
        if not text.strip():
            continue

        results = engine.analyze(text)
        if not results:
            continue

        for result in results:
            placeholder = ENTITY_TO_PLACEHOLDER.get(result.entity_type, "[SENSITIVE_DATA]")
            label = placeholder
            stats[label] = stats.get(label, 0) + 1

            # Strip surrounding whitespace before searching so PyMuPDF finds it
            entity_text = text[result.start : result.end].strip()
            if not entity_text:
                continue

            rects = page.search_for(entity_text)
            for rect in rects:
                page.add_redact_annot(
                    rect,
                    text=placeholder,
                    fontsize=7,
                    fill=(1, 1, 1),       # white fill
                    text_color=(0, 0, 0), # black placeholder text
                )

        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    doc.save(str(output_path))
    doc.close()
    return stats
