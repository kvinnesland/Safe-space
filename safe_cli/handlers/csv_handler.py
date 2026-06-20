import csv
from pathlib import Path
from typing import Dict, Optional

from ..column_rules import placeholder_for_header
from ..engine import AnonymizerCore


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    rows = []
    col_forced: Dict[int, str] = {}
    col_headers: Dict[int, str] = {}

    with open(input_path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        for row_idx, row in enumerate(reader):
            if row_idx == 0:
                # Header row: build column rule maps, pass through unchanged
                for col_idx, cell in enumerate(row):
                    h = cell.strip()
                    if not h:
                        continue
                    forced = placeholder_for_header(h)
                    if forced:
                        col_forced[col_idx] = forced
                    col_headers[col_idx] = h.lower()
                rows.append(row)
                continue

            new_row = []
            for col_idx, cell in enumerate(row):
                if not cell or not cell.strip():
                    new_row.append(cell)
                    continue

                # Forced: whole column is a named PII field
                forced = col_forced.get(col_idx)
                if forced:
                    if cell != forced:
                        stats[forced] = stats.get(forced, 0) + 1
                    new_row.append(forced)
                    continue

                # Standard Presidio pass with context boost from header
                header_text = col_headers.get(col_idx, "")
                if header_text:
                    text = f"{header_text}: {cell}"
                    anon_text, cell_stats = engine.anonymize_text(text)
                    prefix = f"{header_text}: "
                    if anon_text.startswith(prefix):
                        anonymized = anon_text[len(prefix):]
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
