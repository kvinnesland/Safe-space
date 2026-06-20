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
            # Norwegian (bokmål + nynorsk)
            r"\b(diagnos[ei]|sykdom|sjukdom|sykehus|sjukehus|legemiddel|medisinsk?|"
            r"helseopplysning(?:ar)?|allergi|operasjon|innleggelse|poliklinikk|"
            r"rehabilitering|prognose|symptom(?:er)?|kreft|diabetes|"
            r"depresjon|angst|psykisk|psykiatri|psykose|psykolog|"
            r"HIV|AIDS|funksjonshemming|nedsatt\s+funksjonsevne|nedsett\s+funksjonsevne|"
            r"uf[øo]re(?:trygd)?|pasientjournal|legejournal|EPJ|helsejour|"
            r"blodtype|blodtrykk|blodpr[øo]ve|medikament|medisinering|"
            r"beh?andling(?:splan)?|r[øo]ntgen|ultralyd|biopsi|"
            r"MR[\s-]?(?:bilder?)?|CT[\s-]?(?:bilder?)?|"
            r"sykemelding|sjukemelding|sykefrav[æa]r|resept|"
            r"rusbehandling|ADHD|autisme|demens|Alzheimer|epilepsi|astma|"
            # English
            r"diagnosis|diagnoses|cancer|tumo(?:u?r)|prescription|"
            r"medical[\s-]?record|health[\s-]?record|patient[\s-]?record|"
            r"psychiatric|psychiatry|mental[\s-]?health|"
            r"disability|impairment|sick[\s-]?leave|medical[\s-]?leave|"
            r"blood[\s-]?type|blood[\s-]?pressure|allerg[yi]|"
            r"X-ray|MRI[\s-]?scan|CT[\s-]?scan)\b",
            re.I,
        )],
    ),
    (
        "genetiske opplysninger",
        [re.compile(
            r"\b(DNA|genetisk|genetics?|arvelighet|arveleg|hereditary|"
            r"genom(?:e)?|kromosom|chromosome|genmutasjon|mutation|gentest|"
            r"genetic[\s-]?test|BRCA)\b",
            re.I,
        )],
    ),
    (
        "biometriske opplysninger",
        [re.compile(
            r"\b(fingeravtrykk|fingerprint|ansiktsgjenkjenning|"
            r"facial[\s-]?recognition|face[\s-]?recognition|"
            r"iris(?:skann|[\s-]?scan)?|retina(?:[\s-]?scan)?|"
            r"biometrisk?|biometri|biometrics?|"
            r"stemmeavtrykk|voiceprint|voice[\s-]?recognition|"
            r"DNA-profil|ansiktsskann)\b",
            re.I,
        )],
    ),
    (
        "rase eller etnisk opprinnelse",
        [re.compile(
            r"\b(etnisk\s+opprinnelse|etnisk\s+opphav|ethnic[\s-]?origin|ethnicity|"
            r"rasemessig|racial|hudfarge|skin[\s-]?colou?r|"
            r"rase(?:diskriminering)?|nasjonal\s+opprinnelse|nasjonal\s+opphav|"
            r"national[\s-]?origin|minoritet(?:sbakgrunn)?|"
            r"innvandrerbakgrunn|innvandrarbakgrunn)\b",
            re.I,
        )],
    ),
    (
        "politisk oppfatning",
        [re.compile(
            r"\b(politisk\s+(oppfatning|overbevisning|overtyding|syn|tilh[øo]righet)|"
            r"partitilh[øo]righet|partitilh[øo]rsle|partipolitisk|"
            r"stemte?\s+p[åa]|r[øo]ysta\s+p[åa]|"
            r"political[\s-]?(opinion|view|belief|affiliation)|party[\s-]?affiliation|"
            r"Arbeiderparti(?:et)?|H[øo]yre|Fremskrittsparti(?:et)?|"
            r"SV|Senterparti(?:et)?|Venstre|KrF|MDG|R[øo]dt)\b",
            re.I,
        )],
    ),
    (
        "religiøs eller filosofisk overbevisning",
        [re.compile(
            r"\b(trossamfunn|trudomssamfunn|religionsutov|livssyn|konfesjon|"
            r"muslim|kristen|Christian(?:ity)?|jødisk|Jewish|Judaism|"
            r"hindu|buddhist|ateist|atheist|agnostic|Sikh|Sikhism|"
            r"moské|mosque|synagoge|synagogue|kirkemedlem|"
            r"d[åa]p|baptism|omskj[æa]ring|circumcision|"
            r"ramadan|sharia|halal|kosher|frikirke|"
            r"Jehovas\s+vitner|Jehovah['']?s\s+Witness(?:es)?|Mormon)\b",
            re.I,
        )],
    ),
    (
        "fagforeningsmedlemskap",
        [re.compile(
            r"\b(fagforening|fagforeining|fagforbund|fagorganisert|"
            # Hovedorganisasjoner
            r"LO|YS|Unio|Akademikerne|NITO|"
            # Enkeltforbund — LO
            r"Fagforbundet|Fellesforbundet|Industri[\s-]Energi|"
            r"El[\s-]og[\s-]IT[\s-]Forbundet|Handel[\s-]og[\s-]Kontor|"
            r"Fellesorganisasjonen|Transportarbeiderforbundet|"
            # Enkeltforbund — Unio
            r"Utdanningsforbundet|Sykepleierforbundet|Politiets[\s-]Fellesforbund|"
            r"Norsk[\s-]Tjenestemannslag|"
            # Enkeltforbund — Akademikerne
            r"Legeforeningen|Den[\s-]norske[\s-]legeforening|Tekna|Juristforbundet|"
            # Enkeltforbund — YS
            r"Finansforbundet|Negotia|"
            # Generelle termer
            r"tillitsvalgt|tillitsvald|streik(?:erett|rett)?|tariffavtale|"
            r"kollektiv\s+avtale|fagforeningskontingent|"
            r"trade[\s-]?union|labor[\s-]?union|labour[\s-]?union|"
            r"union[\s-]?membership|shop[\s-]?steward|collective[\s-]?bargaining)\b",
            re.I,
        )],
    ),
    (
        "seksuelle forhold eller seksuell orientering",
        [re.compile(
            r"\b(seksuell\s+orientering|sexual[\s-]?orientation|seksualitet|"
            r"homofil|homosexual|lesbisk|lesbian|bifil|bisexual|"
            r"transperson|transgender|kj[øo]nnsidentitet|gender[\s-]?identity|"
            r"kj[øo]nnskorrigering|gender[\s-]?reassignment|kj[øo]nnsskifte|"
            r"LHBT|LGBT(?:Q(?:IA?\+?)?)?|queer|ikke-bin[æa]r|non.?binary|"
            r"intersex|same.?sex)\b",
            re.I,
        )],
    ),
    (
        "straffbare forhold",
        [re.compile(
            r"\b(domfelt|convicted|conviction|straffedom|fengselsstraff|"
            r"prison[\s-]?sentence|imprisonment|incarceration|"
            r"varetektsfengslet|varetektsfengsla|remand(?:\s+custody)?|"
            r"siktelse|indictment|tiltale(?:beslutning)?|b[øo]telagt|b[øo]telagd|"
            r"kriminell\s+bakgrunn|criminal[\s-]?record|criminal[\s-]?background|"
            r"politianmeldelse|straffeattest|"
            r"pr[øo]vel[øo]slatelse|pr[øo]velauslating|parole|probation|"
            r"betinget\s+dom|betinga\s+dom|suspended[\s-]?sentence)\b",
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
