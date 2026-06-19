from pathlib import Path
from typing import Dict

import openpyxl

from ..engine import AnonymizerCore


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    wb = openpyxl.load_workbook(input_path)

    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.strip():
                    anonymized, cell_stats = engine.anonymize_text(cell.value)
                    for k, v in cell_stats.items():
                        stats[k] = stats.get(k, 0) + v
                    cell.value = anonymized

    wb.save(output_path)
    return stats
