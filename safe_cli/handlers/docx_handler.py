from pathlib import Path
from typing import Dict, Optional

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from ..column_rules import placeholder_for_header
from ..engine import AnonymizerCore
from ..media import PLACEHOLDER_IMAGE, PLACEHOLDER_MEDIA


def _remove_embedded_media(body, stats: Dict[str, int]) -> None:
    """
    Replace embedded images (w:drawing), GIFs, OLE objects (w:object),
    and VML images (v:imagedata) with placeholder text runs.
    Works by finding the containing <w:r> and swapping its content.
    """
    # Inline and floating images / GIFs
    for drawing in list(body.iter(qn("w:drawing"))):
        run = drawing.getparent()
        if run is None:
            continue
        run.remove(drawing)
        t = OxmlElement("w:t")
        t.text = PLACEHOLDER_IMAGE
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        run.append(t)
        stats[PLACEHOLDER_IMAGE] = stats.get(PLACEHOLDER_IMAGE, 0) + 1

    # OLE objects — embedded video, audio, spreadsheets, etc.
    for obj in list(body.iter(qn("w:object"))):
        run = obj.getparent()
        if run is None:
            continue
        run.remove(obj)
        t = OxmlElement("w:t")
        t.text = PLACEHOLDER_MEDIA
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        run.append(t)
        stats[PLACEHOLDER_MEDIA] = stats.get(PLACEHOLDER_MEDIA, 0) + 1

    # Legacy VML images (older Word files)
    vml_ns = "urn:schemas-microsoft-com:vml"
    for imagedata in list(body.iter(f"{{{vml_ns}}}imagedata")):
        # Remove the whole <v:shape> ancestor if possible, else just imagedata
        shape = imagedata.getparent()
        while shape is not None and shape.tag != f"{{{vml_ns}}}shape":
            shape = shape.getparent()
        target = shape if shape is not None else imagedata
        parent = target.getparent()
        if parent is not None:
            parent.remove(target)
            stats[PLACEHOLDER_IMAGE] = stats.get(PLACEHOLDER_IMAGE, 0) + 1


def _anonymize_paragraph(
    para,
    engine: AnonymizerCore,
    stats: Dict[str, int],
    forced: Optional[str] = None,
) -> None:
    full_text = para.text
    if not full_text.strip():
        return

    if forced:
        anonymized = forced
        stats[forced] = stats.get(forced, 0) + 1
    else:
        anonymized, para_stats = engine.anonymize_text(full_text)
        for k, v in para_stats.items():
            stats[k] = stats.get(k, 0) + v

    if anonymized == full_text:
        return

    runs = para.runs
    if runs:
        for run in runs[1:]:
            run._r.getparent().remove(run._r)
        runs[0].text = anonymized
    else:
        para.add_run(anonymized)


def _process_table(table, engine: AnonymizerCore, stats: Dict[str, int]) -> None:
    rows = table.rows
    if not rows:
        return

    col_forced: Dict[int, Optional[str]] = {}
    for col_idx, cell in enumerate(rows[0].cells):
        col_forced[col_idx] = placeholder_for_header(cell.text.strip())

    for row_idx, row in enumerate(rows):
        for col_idx, cell in enumerate(row.cells):
            forced = col_forced.get(col_idx) if row_idx > 0 else None
            for para in cell.paragraphs:
                _anonymize_paragraph(para, engine, stats, forced=forced)


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    doc = Document(str(input_path))

    # Remove all embedded media first (images, GIFs, video, audio)
    _remove_embedded_media(doc.element.body, stats)

    for para in doc.paragraphs:
        _anonymize_paragraph(para, engine, stats)

    for table in doc.tables:
        _process_table(table, engine, stats)

    for section in doc.sections:
        for hf in (
            section.header, section.footer,
            section.first_page_header, section.first_page_footer,
            section.even_page_header, section.even_page_footer,
        ):
            if hf is not None:
                _remove_embedded_media(hf._element, stats)
                for para in hf.paragraphs:
                    _anonymize_paragraph(para, engine, stats)

    doc.save(str(output_path))
    return stats
