import csv
from pathlib import Path
from typing import Dict

from ..engine import AnonymizerCore


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    rows = []
    col_headers: Dict[int, str] = {}

    with open(input_path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        for row_idx, row in enumerate(reader):
            if row_idx == 0:
                # Header row: capture for context, pass through unchanged
                col_headers = {i: cell.strip().lower() for i, cell in enumerate(row) if cell.strip()}
                rows.append(row)
                continue

            new_row = []
            for col_idx, cell in enumerate(row):
                if not cell or not cell.strip():
                    new_row.append(cell)
                    continue

                header = col_headers.get(col_idx, "")
                if header:
                    text = f"{header}: {cell}"
                    anonymized_text, cell_stats = engine.anonymize_text(text)
                    prefix = f"{header}: "
                    if anonymized_text.startswith(prefix):
                        anonymized = anonymized_text[len(prefix):]
                    else:
                        anonymized, cell_stats = engine.anonymize_text(cell)
                else:
                    anonymized, cell_stats = engine.anonymize_text(cell)

                for k, v in cell_stats.items():
                    stats[k] = stats.get(k, 0) + v
                new_row.append(anonymized)
            rows.append(new_row)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    return stats
