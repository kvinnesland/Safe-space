"""Core anonymization engine — Presidio with Norwegian + English dual-language analysis."""

import re
from typing import Dict, List, Tuple

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from .norwegian import get_norwegian_recognizers

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
    "DATE_TIME": "[DATE_OF_BIRTH]",
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
    "URL": "[SENSITIVE_DATA]",
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
            "No spaCy model found. Build the Docker image first:\n"
            "  docker compose build"
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
            # Norwegian model adds PER/LOC/ORG entities missed by the English model.
            # Pattern recognizers (phone, fnr, email…) are already covered by the en pass.
            nb_results = self._analyzer.analyze(
                text=text,
                language="nb",
                entities=["PERSON", "LOCATION", "NRP"],
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
