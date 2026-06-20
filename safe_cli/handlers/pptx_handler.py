from pathlib import Path
from typing import Dict, Optional

from pptx import Presentation

from ..column_rules import placeholder_for_header
from ..engine import AnonymizerCore


def _anonymize_text_frame(
    tf,
    engine: AnonymizerCore,
    stats: Dict[str, int],
    forced: Optional[str] = None,
) -> None:
    for para in tf.paragraphs:
        if not para.runs:
            continue
        full_text = "".join(run.text for run in para.runs)
        if not full_text.strip():
            continue

        if forced:
            anonymized = forced
            stats[forced] = stats.get(forced, 0) + 1
        else:
            anonymized, cell_stats = engine.anonymize_text(full_text)
            for k, v in cell_stats.items():
                stats[k] = stats.get(k, 0) + v

        if anonymized == full_text:
            continue

        para.runs[0].text = anonymized
        for run in para.runs[1:]:
            run.text = ""


def _process_table(table, engine: AnonymizerCore, stats: Dict[str, int]) -> None:
    rows = list(table.rows)
    if not rows:
        return

    # Build forced-placeholder map from first row (header row)
    col_forced: Dict[int, Optional[str]] = {}
    for col_idx, cell in enumerate(rows[0].cells):
        header = cell.text_frame.text.strip()
        col_forced[col_idx] = placeholder_for_header(header)

    for row_idx, row in enumerate(rows):
        for col_idx, cell in enumerate(row.cells):
            forced = col_forced.get(col_idx) if row_idx > 0 else None
            _anonymize_text_frame(cell.text_frame, engine, stats, forced=forced)


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    prs = Presentation(str(input_path))

    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                _anonymize_text_frame(shape.text_frame, engine, stats)
            if shape.has_table:
                _process_table(shape.table, engine, stats)

    prs.save(str(output_path))
    return stats
