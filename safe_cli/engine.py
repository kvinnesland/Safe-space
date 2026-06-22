"""Core anonymization engine — Presidio with Norwegian + English dual-language analysis."""

import re
from typing import Dict, List, Tuple

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from .norwegian import get_norwegian_recognizers
from .name_lists import NORWEGIAN_COMMON_WORDS, NORWEGIAN_NAMES

# Maps Presidio entity types to the placeholders written into anonymized output
ENTITY_TO_PLACEHOLDER: Dict[str, str] = {
    "PERSON": "[NAME]",
    "EMAIL_ADDRESS": "[EMAIL]",
    "PHONE_NUMBER": "[PHONE]",
    "NO_PHONE": "[PHONE]",
    "LOCATION": "[ADDRESS]",
    "NO_ADDRESS": "[ADDRESS]",
    "CREDIT_CARD": "[CREDIT_CARD]",
    "IP_ADDRESS": "[IP_ADDRESS]",
    "DATE_TIME": "[DATO]",
    "IBAN_CODE": "[ACCOUNT_NUMBER]",
    "NO_BANK_ACCOUNT": "[ACCOUNT_NUMBER]",
    "NO_FODSELSNUMMER": "[FØDSELSNUMMER]",
    "NO_ORG_NUMBER": "[ORGNUMMER]",
    "NO_HEALTH_INFO": "[HEALTH_INFO]",
    "MEDICAL_LICENSE": "[HEALTH_INFO]",
    "NRP": "[NAME]",
    "US_SSN": "[FØDSELSNUMMER]",
    "UK_NHS": "[HEALTH_INFO]",
    "US_PASSPORT": "[SENSITIVE_DATA]",
    "US_DRIVER_LICENSE": "[SENSITIVE_DATA]",
    "IN_PAN": "[SENSITIVE_DATA]",
    "SG_NRIC_FIN": "[SENSITIVE_DATA]",
    "AU_ABN": "[ORGNUMMER]",
    "AU_ACN": "[ORGNUMMER]",
    "NO_DATE": "[DATO]",
    "NO_STREET_ADDRESS": "[ADRESSE]",
    "NO_POSTAL_CODE": "[POSTNUMMER]",
    "NO_CITY": "[POSTSTED]",
}

ENTITIES = list(ENTITY_TO_PLACEHOLDER.keys())

# Low threshold: err on side of caution for GDPR compliance
CONFIDENCE_THRESHOLD = 0.4

# 4-digit years (19xx / 20xx) are misclassified as LOCATION/NO_ADDRESS by the NER model.
# _YEAR_RE: exact match (e.g. bare "2024" tagged as LOCATION)
# _YEAR_RE_START: span starts with a year (e.g. "2024 Angående" from postal-code pattern)
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")
_YEAR_RE_START = re.compile(r"^(19|20)\d{2}\b")
# Customer/employee IDs like KN-002 or A-101 misclassified as LOCATION
_ID_RE = re.compile(r"^[A-Za-z]{1,4}[-/]\d{1,6}[A-Za-z]?$")

# Words that should never be tagged as PERSON — combination of the
# property-specific list (rooms, materials, headings) and the general
# Norwegian vocabulary imported from name_lists.py.
_NO_PERSON_DENYLIST: frozenset = frozenset({
    # Rooms and areas
    "etasje", "plan", "rom", "soverom", "stue", "kjøkken", "bad", "badrom",
    "baderom", "vaskerom", "toalettrom", "wc", "gang", "entre", "entré",
    "bod", "garasje", "loft", "loftstue", "balkong", "veranda", "terrasse",
    "korridor", "hall", "vindfang", "trapperom",
    # Building / property types
    "bygg", "bygning", "blokk", "bolig", "leilighet", "enebolig", "rekkehus",
    "tomannsbolig", "hytte", "tomt", "eiendom", "sameie", "borettslag",
    "seksjon", "fellesareal", "uteareal",
    # Property-document headings
    "innvendig", "utvendig", "generelt", "oppsummering", "kommentar",
    "vurdering", "konsekvens", "tiltak", "avvik", "beskrivelse", "standard",
    "tilstand", "vedlikehold", "innredning", "overflater", "installasjoner",
    "parkering", "lagring", "renovasjon",
    # Materials / surfaces
    "parkett", "flis", "laminat", "maling", "betong", "gips", "stein",
    "marmor", "treverk", "puss",
    # Building elements
    "vindu", "dør", "innerdør", "ytterdør", "balkongdør", "port", "leddport",
    "tak", "gulv", "himling", "vegg", "mur", "trapp", "rekkverk",
    "gelender", "søyle", "kledning", "fasade",
    # Cardinal directions
    "nord", "sør", "øst", "vest", "nordøst", "nordvest", "sørøst", "sørvest",
    # Real estate process terms
    "megler", "selger", "kjøper", "eier", "leietaker", "utleier",
    "takst", "salg", "kjøp", "bud", "oppdrag",
    # Administrative
    "kommune", "fylke", "sted", "tettsted",
}) | NORWEGIAN_COMMON_WORDS  # merge with general Norwegian vocabulary

# Norwegian compound-noun suffixes that never end a person name.
# Catches long compound nouns that aren't in the denylist above.
_NO_COMPOUND_NOUN_SUFFIX = re.compile(
    r"(arealer?|forhold|konstruksjon|skille[r]?|tekking|"
    r"analyse[n]?|rapport(?:en)?|grader?|gradene|måte[n]?|åpner|"
    r"deler?|tilstand(?:en)?|sjon(?:en|er|ene)?|installasjoner?|"
    r"forutsetninger?|leiligheten?|eiendommen?|"
    r"kart(?:et)?|forsikring(?:en|er|ene)?|forvaltning(?:en)?|"
    r"endring(?:en|er|ene)?|antydning(?:en)?|beskrivelse[n]?|"
    r"avtale[n]?|plikt(?:en)?)$",
    re.IGNORECASE | re.UNICODE,
)

# Lowercase particles that can appear inside a multi-word name (van, de, …)
_NAME_PARTICLES = frozenset({
    "van", "de", "von", "af", "av", "der", "den", "el", "al", "la", "le",
})

# DATE_TIME false-positive: prepositions that follow a noun cause the NER
# to tag "noun + fra/til/…" as a date ("eierleilighet fra 2019").
_DATE_FP_LEADING_PREP = re.compile(
    r"^(?:[A-Za-zÆØÅæøå]+\s+)?(fra|til|siden|innen|etter|before|after|from|since)\b",
    re.IGNORECASE,
)


def _load_available_models() -> List[Dict[str, str]]:
    """Find the best available spaCy model for each supported language."""
    import spacy

    found = []
    for lang, candidates in [
        ("nb", ["nb_core_news_lg", "nb_core_news_md", "nb_core_news_sm"]),
        ("en", ["en_core_web_lg", "en_core_web_md", "en_core_web_sm"]),
    ]:
        for model in candidates:
            try:
                spacy.load(model)
                found.append({"lang_code": lang, "model_name": model})
                break
            except OSError:
                continue

    if not found:
        raise RuntimeError(
            "No spaCy model found. Run setup first:\n"
            "  Windows: .\\setup.ps1\n"
            "  Mac/Linux: bash setup.sh"
        )
    return found


def _merge_results(primary: list, secondary: list) -> list:
    """Combine two result lists; for overlapping spans keep the higher-confidence one."""
    combined = list(primary) + list(secondary)
    combined.sort(key=lambda r: r.score, reverse=True)
    kept = []
    for result in combined:
        if not any(
            max(result.start, r.start) < min(result.end, r.end)
            for r in kept
        ):
            kept.append(result)
    return kept


def _filter_false_positives(results: list, text: str) -> list:
    """Drop known false-positive patterns before anonymization."""
    out = []
    for r in results:
        chunk = text[r.start : r.end]
        stripped = chunk.strip()
        # Years like "2024" tagged as LOCATION
        if r.entity_type in ("LOCATION", "NO_ADDRESS") and _YEAR_RE.match(stripped):
            continue
        if r.entity_type == "NO_ADDRESS" and _YEAR_RE_START.match(stripped):
            continue
        # Short ID codes like "KN-002" tagged as LOCATION/PERSON
        if r.entity_type in ("LOCATION", "PERSON", "NRP") and _ID_RE.match(stripped):
            continue
        # ALL-CAPS abbreviations (DNS, API, …) tagged as PERSON/NRP
        if r.entity_type in ("PERSON", "NRP") and len(stripped) >= 2 and stripped.isupper():
            continue
        if r.entity_type in ("PERSON", "NRP"):
            # Common Norwegian nouns misclassified as person names by NER
            if stripped.lower() in _NO_PERSON_DENYLIST:
                continue
            # Single-token match ≤ 4 chars: skip unless it's a known Norwegian name.
            # This catches short prepositions/articles ("den", "fra", "og") while
            # allowing real short names like Per, Ole, Tor, Åse through.
            if " " not in stripped and len(stripped) <= 4:
                if stripped not in NORWEGIAN_NAMES:
                    continue
            # Single-word compound nouns identified by suffix (never person names)
            if " " not in stripped and _NO_COMPOUND_NOUN_SUFFIX.search(stripped):
                continue
            # Multi-word spans: keep only if every token starts with a capital
            # letter (or is a known lowercase particle like "van", "de", "von"),
            # AND no individual token is itself a known non-name word.
            # This eliminates sentence fragments ("det kort vei til skole",
            # "butikk og busstopp") and heading pairs ("Takkonstruksjon/ Loft").
            if " " in stripped:
                tokens = stripped.split()
                if not all(
                    (bool(w) and w[0].isupper()) or w.lower() in _NAME_PARTICLES
                    for w in tokens
                ):
                    continue
                clean = [re.sub(r"[^\w]", "", w, flags=re.UNICODE) for w in tokens]
                if any(
                    c.lower() in _NO_PERSON_DENYLIST
                    or (bool(c) and _NO_COMPOUND_NOUN_SUFFIX.search(c))
                    for c in clean
                ):
                    continue
        if r.entity_type == "LOCATION":
            # Latin Extended-B characters (U+0180–U+024F) indicate a custom PDF
            # font that couldn't be decoded — the text is unreadable, not a location.
            if any("ƀ" <= c <= "ɏ" for c in stripped):
                continue
            # PDF private-use-area characters (custom font encoding artifacts)
            if any("" <= c <= "" for c in stripped):
                continue
            # Spans containing newlines are PDF extraction artifacts, not addresses
            if "\n" in stripped:
                continue
            # ALL-CAPS short abbreviations (NS, UK, EL, ...) are not locations
            if len(stripped) <= 4 and stripped.isupper():
                continue
            # Common Norwegian words tagged as locations by NER.
            # Strip trailing punctuation so "vinskap," matches "vinskap".
            clean_stripped = stripped.rstrip(".,;:!?-")
            if clean_stripped.lower() in _NO_PERSON_DENYLIST:
                continue
            # Compound noun suffixes never end a location name
            if " " not in clean_stripped and _NO_COMPOUND_NOUN_SUFFIX.search(clean_stripped):
                continue
            # Multi-word location spans: every token must start with a capital
            # (filters "membran og", "til ny", "Kjøper og", "inn bud", etc.)
            if " " in stripped:
                tokens = stripped.split()
                if not all(
                    (bool(w) and w[0].isupper()) or w.lower() in _NAME_PARTICLES
                    for w in tokens
                ):
                    continue
        # NO_ADDRESS spans containing newlines are pattern misfires across
        # PDF field boundaries (e.g. "9020\nPoststed\nTromsdalen").
        if r.entity_type == "NO_ADDRESS" and "\n" in stripped:
            continue
        # DATE_TIME false-positive: "noun fra/til year" is not a date.
        if r.entity_type == "DATE_TIME" and _DATE_FP_LEADING_PREP.search(stripped):
            continue
        out.append(r)
    return out


class AnonymizerCore:
    """Dual-language (Norwegian + English) PII anonymization engine."""

    def __init__(self):
        models = _load_available_models()
        lang_codes = {m["lang_code"] for m in models}

        nlp_engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": models,
            }
        ).create_engine()

        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(nlp_engine=nlp_engine)
        for recognizer in get_norwegian_recognizers():
            registry.add_recognizer(recognizer)

        self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine, registry=registry)
        self._anonymizer = AnonymizerEngine()
        self._has_nb = "nb" in lang_codes
        self._has_en = "en" in lang_codes
        self._operators: Dict[str, OperatorConfig] = {
            entity_type: OperatorConfig("replace", {"new_value": placeholder})
            for entity_type, placeholder in ENTITY_TO_PLACEHOLDER.items()
        }

    def analyze(self, text: str) -> list:
        """
        Run PII analysis in all available languages and merge results.
        English pass: all pattern recognizers + English NER.
        Norwegian pass: Norwegian NER (catches names/places the English model misses).
        """
        results: list = []

        if self._has_en:
            results = list(
                self._analyzer.analyze(
                    text=text,
                    language="en",
                    entities=ENTITIES,
                    score_threshold=CONFIDENCE_THRESHOLD,
                )
            )

        if self._has_nb:
            # Norwegian model adds PERSON/LOC entities missed by the English model.
            # NRP (nationalities/groups) is intentionally excluded: it maps to [NAME]
            # but nationalities are not person names and cause many false positives.
            # Pattern recognizers (phone, fnr, email…) are already covered by the en pass.
            nb_results = self._analyzer.analyze(
                text=text,
                language="nb",
                entities=["PERSON", "LOCATION"],
                score_threshold=CONFIDENCE_THRESHOLD,
            )
            results = _merge_results(results, list(nb_results))

        return _filter_false_positives(results, text)

    def anonymize_text(self, text: str) -> Tuple[str, Dict[str, int]]:
        """
        Anonymize all PII in text.
        Returns (anonymized_text, {placeholder_label: count}).
        """
        if not text or not text.strip():
            return text, {}

        results = self.analyze(text)
        if not results:
            return text, {}

        stats: Dict[str, int] = {}
        for r in results:
            label = ENTITY_TO_PLACEHOLDER.get(r.entity_type, "[SENSITIVE_DATA]")
            stats[label] = stats.get(label, 0) + 1

        anonymized = self._anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=self._operators,
        )
        return anonymized.text, stats
