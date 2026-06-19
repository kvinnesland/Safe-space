import csv
from pathlib import Path
from typing import Dict

from ..engine import AnonymizerCore


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    rows = []

    with open(input_path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            new_row = []
            for cell in row:
                if cell and cell.strip():
                    anonymized, cell_stats = engine.anonymize_text(cell)
                    for k, v in cell_stats.items():
                        stats[k] = stats.get(k, 0) + v
                    new_row.append(anonymized)
                else:
                    new_row.append(cell)
            rows.append(new_row)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    return stats
