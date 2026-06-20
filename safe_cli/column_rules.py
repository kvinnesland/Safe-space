"""
Column-header-based forced anonymization rules.

If a column header matches one of these patterns the ENTIRE column is
anonymized with the mapped placeholder — Presidio is not consulted for
those cells. This catches structured data where the header makes the
sensitivity unambiguous (e.g. a column literally called "Fødselsnummer").
"""

import re
from typing import Optional

# (compiled pattern, placeholder) — checked in order; first match wins.
# Patterns are matched case-insensitively against the stripped header text.
_RULES = [
    # ── Norwegian national ID ───────────────────────────────────────────
    (re.compile(r"f[øo]dselsnummer|fnr\.?|personnummer|person[\s._-]?nr|person[\s._-]?id", re.I),
     "[FØDSELSNUMMER]"),

    # ── Name ────────────────────────────────────────────────────────────
    (re.compile(r"(for|sur|etter|mellomnavn|full[\s._-]?)?navn|name|full[\s._-]?name", re.I),
     "[NAME]"),

    # ── Phone ───────────────────────────────────────────────────────────
    (re.compile(r"(mobil|tele)?fon\.?|tlf\.?|mob\.?|phone|mobile|cell", re.I),
     "[PHONE]"),

    # ── Email ───────────────────────────────────────────────────────────
    (re.compile(r"e[\s._-]?post|e[\s._-]?mail|mail", re.I),
     "[EMAIL]"),

    # ── Address ─────────────────────────────────────────────────────────
    (re.compile(r"adresse|address|gateadr|bostedsadr|postadresse", re.I),
     "[ADDRESS]"),
    (re.compile(r"postnummer|post[\s._-]?nr|zip|postal[\s._-]?code", re.I),
     "[ADDRESS]"),
    (re.compile(r"poststed|by|city", re.I),
     "[ADDRESS]"),

    # ── Date of birth ────────────────────────────────────────────────────
    (re.compile(r"f[øo]dselsdato|birth[\s._-]?date|dob|f[øo]dt", re.I),
     "[DATE_OF_BIRTH]"),

    # ── Bank account ─────────────────────────────────────────────────────
    (re.compile(r"konto(nummer)?|bankkonto|kontonr|account[\s._-]?(no|number|nr)?", re.I),
     "[ACCOUNT_NUMBER]"),

    # ── Organisation number ──────────────────────────────────────────────
    (re.compile(r"org(anisasjons)?[\s._-]?(nr|nummer)|orgnr|org\.nr", re.I),
     "[ORGNUMMER]"),

    # ── Credit card ──────────────────────────────────────────────────────
    (re.compile(r"kredittkort|credit[\s._-]?card|kortnr|card[\s._-]?(no|number)", re.I),
     "[CREDIT_CARD]"),

    # ── IP address ───────────────────────────────────────────────────────
    (re.compile(r"ip[\s._-]?(adresse|address)", re.I),
     "[IP_ADDRESS]"),

    # ── Employee / person reference ──────────────────────────────────────
    (re.compile(r"ansatt[\s._-]?nr|employee[\s._-]?(id|no)|emp[\s._-]?id|personaln[ru]", re.I),
     "[SENSITIVE_DATA]"),

    # ── GDPR Article 9 special categories ───────────────────────────────
    (re.compile(r"diagnose|sykdom|helse(oppl)?|medisin|behandling|journal", re.I),
     "[HEALTH_INFO]"),
    (re.compile(r"genetisk|dna|genom", re.I),
     "[HEALTH_INFO]"),
    (re.compile(r"biometr|fingeravtrykk|ansiktsgjenkjenning", re.I),
     "[HEALTH_INFO]"),
    (re.compile(r"religion|trossamfunn|livssyn|konfesjon", re.I),
     "[HEALTH_INFO]"),
    (re.compile(r"fagforening|fagforbund|tillitsvalgt", re.I),
     "[HEALTH_INFO]"),
    (re.compile(r"politisk|parti(tillh|tilknyt)?", re.I),
     "[HEALTH_INFO]"),
    (re.compile(r"etnisitet|etnisk|rase|opprinnelse", re.I),
     "[HEALTH_INFO]"),
    (re.compile(r"seksuell|seksualitet|kj[øo]nnsidentitet|lhbt", re.I),
     "[HEALTH_INFO]"),
    (re.compile(r"straff|dom(fellt)?|siktelse|fengsel|lovbrudd", re.I),
     "[HEALTH_INFO]"),
]


def placeholder_for_header(header: str) -> Optional[str]:
    """
    Return the forced placeholder if the header unambiguously names a PII field.
    Returns None if the header does not match any rule.
    """
    h = header.strip()
    if not h:
        return None
    for pattern, placeholder in _RULES:
        if pattern.search(h):
            return placeholder
    return None
