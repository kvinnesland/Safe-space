from pathlib import Path
from typing import Dict

from docx import Document

from ..engine import AnonymizerCore


def _anonymize_paragraph(para, engine: AnonymizerCore, stats: Dict[str, int]) -> None:
    full_text = para.text
    if not full_text.strip():
        return

    anonymized, para_stats = engine.anonymize_text(full_text)
    for k, v in para_stats.items():
        stats[k] = stats.get(k, 0) + v

    if anonymized == full_text:
        return

    # Replace content: keep the first run's formatting, drop the rest
    runs = para.runs
    if runs:
        for run in runs[1:]:
            run._r.getparent().remove(run._r)
        runs[0].text = anonymized
    else:
        para.add_run(anonymized)


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    doc = Document(str(input_path))

    for para in doc.paragraphs:
        _anonymize_paragraph(para, engine, stats)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    _anonymize_paragraph(para, engine, stats)

    for section in doc.sections:
        for hf in (
            section.header,
            section.footer,
            section.first_page_header,
            section.first_page_footer,
            section.even_page_header,
            section.even_page_footer,
        ):
            if hf is not None:
                for para in hf.paragraphs:
                    _anonymize_paragraph(para, engine, stats)

    doc.save(str(output_path))
    return stats
