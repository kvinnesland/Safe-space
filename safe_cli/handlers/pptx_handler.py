from pathlib import Path
from typing import Dict

from pptx import Presentation
from pptx.util import Pt

from ..engine import AnonymizerCore


def _anonymize_text_frame(tf, engine: AnonymizerCore, stats: Dict[str, int]) -> None:
    for para in tf.paragraphs:
        if not para.runs:
            continue

        # Collect full paragraph text across all runs
        full_text = "".join(run.text for run in para.runs)
        if not full_text.strip():
            continue

        anonymized, cell_stats = engine.anonymize_text(full_text)
        for k, v in cell_stats.items():
            stats[k] = stats.get(k, 0) + v

        if anonymized == full_text:
            continue

        # Write anonymized text into the first run, clear the rest.
        # Preserves paragraph-level formatting (font, size, color of first run).
        para.runs[0].text = anonymized
        for run in para.runs[1:]:
            run.text = ""


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    prs = Presentation(str(input_path))

    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                _anonymize_text_frame(shape.text_frame, engine, stats)

            # Tables
            if shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        _anonymize_text_frame(cell.text_frame, engine, stats)

    prs.save(str(output_path))
    return stats
