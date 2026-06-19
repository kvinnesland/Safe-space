from pathlib import Path
from typing import Dict

import openpyxl

from ..engine import AnonymizerCore


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    wb = openpyxl.load_workbook(input_path)

    for sheet in wb.worksheets:
        # Capture column headers from row 1 (lowercased) for context-boosted recognition
        col_headers: Dict[int, str] = {}
        for cell in next(sheet.iter_rows(min_row=1, max_row=1), []):
            if isinstance(cell.value, str) and cell.value.strip():
                col_headers[cell.column] = cell.value.strip().lower()

        for row_idx, row in enumerate(sheet.iter_rows(), start=1):
            for cell in row:
                if not isinstance(cell.value, str) or not cell.value.strip():
                    continue

                value = cell.value
                header = col_headers.get(cell.column, "")

                if header and row_idx > 1:
                    # Prepend column header so recognizers with context lists get the boost
                    text = f"{header}: {value}"
                    anonymized_text, cell_stats = engine.anonymize_text(text)
                    prefix = f"{header}: "
                    if anonymized_text.startswith(prefix):
                        anonymized = anonymized_text[len(prefix):]
                    else:
                        # Prefix was modified — re-run without it to avoid corrupt output
                        anonymized, cell_stats = engine.anonymize_text(value)
                else:
                    anonymized, cell_stats = engine.anonymize_text(value)

                for k, v in cell_stats.items():
                    stats[k] = stats.get(k, 0) + v
                if anonymized != value:
                    cell.value = anonymized

    wb.save(output_path)
    return stats
