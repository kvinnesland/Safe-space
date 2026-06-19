from pathlib import Path
from typing import Dict

from ..engine import AnonymizerCore


def _read(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    text = _read(input_path)
    anonymized, stats = engine.anonymize_text(text)
    output_path.write_text(anonymized, encoding="utf-8")
    return stats
