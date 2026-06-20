from pathlib import Path
from typing import Dict, Optional

import openpyxl

from ..column_rules import placeholder_for_header
from ..engine import AnonymizerCore


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    wb = openpyxl.load_workbook(input_path)

    for sheet in wb.worksheets:
        # Build two column maps from row 1:
        #   col_forced[col]  → placeholder to use for the ENTIRE column (header match)
        #   col_headers[col] → header text for Presidio context boost
        col_forced: Dict[int, str] = {}
        col_headers: Dict[int, str] = {}

        for cell in next(sheet.iter_rows(min_row=1, max_row=1), []):
            if not isinstance(cell.value, str) or not cell.value.strip():
                continue
            header = cell.value.strip()
            forced = placeholder_for_header(header)
            if forced:
                col_forced[cell.column] = forced
            col_headers[cell.column] = header.lower()

        for row_idx, row in enumerate(sheet.iter_rows(), start=1):
            for cell in row:
                if not isinstance(cell.value, str) or not cell.value.strip():
                    continue

                value = cell.value

                # Row 1 is the header row — never anonymize the headers themselves
                if row_idx == 1:
                    continue

                # Forced anonymization: column header unambiguously names a PII type
                forced = col_forced.get(cell.column)
                if forced:
                    if value != forced:
                        stats[forced] = stats.get(forced, 0) + 1
                        cell.value = forced
                    continue

                # Standard Presidio pass with column-header context boost
                header_text = col_headers.get(cell.column, "")
                if header_text:
                    text = f"{header_text}: {value}"
                    anon_text, cell_stats = engine.anonymize_text(text)
                    prefix = f"{header_text}: "
                    if anon_text.startswith(prefix):
                        anonymized = anon_text[len(prefix):]
                    else:
                        anonymized, cell_stats = engine.anonymize_text(value)
                else:
                    anonymized, cell_stats = engine.anonymize_text(value)

                for k, v in cell_stats.items():
                    stats[k] = stats.get(k, 0) + v
                if anonymized != value:
                    cell.value = anonymized

    wb.save(output_path)
    return stats
