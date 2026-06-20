"""
GDPR Article 9 — special category content detection.

Scans the full document text for keywords that suggest the presence of
particularly sensitive personal data. Returns a list of detected category
names so the caller can warn the user that manual review is required
before sharing the file outside EU/EEA.
"""

import re
from pathlib import Path
from typing import List

# Each entry: (category_label, [compiled patterns])
# A category is flagged if ANY pattern matches anywhere in the document.
# Patterns deliberately broad — false positives are preferable to false negatives
# for Article 9 content (GDPR recital 51).
_CATEGORIES = [
    (
        "helseopplysninger",
        [re.compile(
            r"\b(diagnos[ei]|sykdom|sykehus|legemiddel|medisinsk?|"
            r"helseopplysning|allergi|operasjon|innleggelse|poliklinikk|"
            r"rehabilitering|prognose|symptom(?:er)?|kreft|diabetes|"
            r"depresjon|angst|psykisk|psykiatri|HIV|AIDS|"
            r"funksjonshemming|nedsatt\s+funksjonsevne|uf[øo]re|"
            r"pasientjournal|EPJ|helsejour|blodtype|blodtrykk|"
            r"medikament|beh?andling(?:splan)?|r[øo]ntgen|MR[\s-]?(?:bilder?)?|CT[\s-]?(?:bilder?)?)\b",
            re.I,
        )],
    ),
    (
        "genetiske opplysninger",
        [re.compile(r"\b(DNA|genetisk|arvelighet|genom|kromosom|genmutasjon|gentest)\b", re.I)],
    ),
    (
        "biometriske opplysninger",
        [re.compile(
            r"\b(fingeravtrykk|ansiktsgjenkjenning|iris(?:skann)?|retina|"
            r"biometr|stemmeavtrykk|DNA-profil|ansiktsskann)\b",
            re.I,
        )],
    ),
    (
        "rase eller etnisk opprinnelse",
        [re.compile(
            r"\b(etnisk\s+opprinnelse|rasemessig|hudfarge|rase(?:diskriminering)?|"
            r"nasjonal\s+opprinnelse|minoritet(?:sbakgrunn)?|innvandrerbakgrunn)\b",
            re.I,
        )],
    ),
    (
        "politisk oppfatning",
        [re.compile(
            r"\b(politisk\s+(oppfatning|overbevisning|syn|tilh[øo]righet)|"
            r"partitilh[øo]righet|partipolitisk|stemte?\s+p[åa]|"
            r"Arbeiderparti(?:et)?|H[øo]yre|Fremskrittsparti(?:et)?|"
            r"SV|Senterparti(?:et)?|Venstre|KrF|MDG|R[øo]dt)\b",
            re.I,
        )],
    ),
    (
        "religiøs eller filosofisk overbevisning",
        [re.compile(
            r"\b(trossamfunn|religionsutov|livssyn|konfesjon|"
            r"muslim|kristen|jødisk|hindu|buddhist|ateist|"
            r"moské|synagoge|kirkemedlem|d[åa]p|omskj[æa]ring|"
            r"ramadan|sharia|halal|kosher|frikirke)\b",
            re.I,
        )],
    ),
    (
        "fagforeningsmedlemskap",
        [re.compile(
            r"\b(fagforening|fagforbund|fagorganisert|"
            r"\bLO\b|\bYS\b|\bUnio\b|\bAkademikerne\b|"
            r"tillitsvalgt|streik(?:erett)?|tariffavtale|"
            r"kollektiv\s+avtale|fagforeningskontingent)\b",
            re.I,
        )],
    ),
    (
        "seksuelle forhold eller seksuell orientering",
        [re.compile(
            r"\b(seksuell\s+orientering|seksualitet|homofil|lesbisk|"
            r"bifil|transperson|kj[øo]nnsidentitet|kj[øo]nnskorrigering|"
            r"\bLHBT\b|\bLGBT\b|queer|ikke-bin[æa]r)\b",
            re.I,
        )],
    ),
    (
        "straffbare forhold",
        [re.compile(
            r"\b(domfelt|straffedom|fengselsstraff|varetektsfengslet|"
            r"siktelse|tiltale(?:beslutning)?|b[øo]telagt|"
            r"kriminell\s+bakgrunn|politianmeldelse|straffeattest|"
            r"pr[øo]vel[øo]slatelse|betinget\s+dom)\b",
            re.I,
        )],
    ),
]


def _extract_full_text(path: Path, suffix: str) -> str:
    """Extract all text from the file for Article 9 scanning."""
    try:
        if suffix in (".txt", ".csv"):
            return path.read_text(encoding="utf-8-sig", errors="replace")

        if suffix == ".pdf":
            import fitz
            doc = fitz.open(str(path))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text

        if suffix == ".docx":
            from docx import Document
            doc = Document(str(path))
            parts = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        parts.extend(p.text for p in cell.paragraphs)
            return "\n".join(parts)

        if suffix == ".xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            parts = []
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    parts.extend(str(c) for c in row if isinstance(c, str) and c)
            wb.close()
            return " ".join(parts)

        if suffix == ".pptx":
            from pptx import Presentation
            prs = Presentation(str(path))
            parts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        parts.append(shape.text_frame.text)
                    if shape.has_table:
                        for row in shape.table.rows:
                            for cell in row.cells:
                                parts.append(cell.text_frame.text)
            return " ".join(parts)

    except Exception:
        pass
    return ""


def scan(path: Path, suffix: str) -> List[str]:
    """
    Scan the document for GDPR Article 9 special category content.
    Returns a list of detected category labels (empty if none found).
    """
    text = _extract_full_text(path, suffix)
    if not text.strip():
        return []

    return [
        label
        for label, patterns in _CATEGORIES
        if any(p.search(text) for p in patterns)
    ]
