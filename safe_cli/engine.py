"""Core anonymization engine — Presidio with Norwegian PII extensions."""

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
}

ENTITIES = list(ENTITY_TO_PLACEHOLDER.keys())

# Low threshold: err on side of caution for GDPR compliance
CONFIDENCE_THRESHOLD = 0.4


def _pick_spacy_model() -> str:
    """Use the largest available spaCy English model for best NER accuracy."""
    import spacy

    for model in ("en_core_web_lg", "en_core_web_md", "en_core_web_sm"):
        try:
            spacy.load(model)
            return model
        except OSError:
            continue
    raise RuntimeError(
        "No spaCy English model found. Run inside Docker or: "
        "python -m spacy download en_core_web_lg"
    )


class AnonymizerCore:
    """Presidio-backed PII anonymization engine with Norwegian extensions."""

    def __init__(self):
        model = _pick_spacy_model()
        nlp_engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": model}],
            }
        ).create_engine()

        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(nlp_engine=nlp_engine)
        for recognizer in get_norwegian_recognizers():
            registry.add_recognizer(recognizer)

        self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine, registry=registry)
        self._anonymizer = AnonymizerEngine()
        self._operators: Dict[str, OperatorConfig] = {
            entity_type: OperatorConfig("replace", {"new_value": placeholder})
            for entity_type, placeholder in ENTITY_TO_PLACEHOLDER.items()
        }

    def analyze(self, text: str) -> list:
        """Return raw Presidio results with character-span positions."""
        return self._analyzer.analyze(
            text=text,
            language="en",
            entities=ENTITIES,
            score_threshold=CONFIDENCE_THRESHOLD,
        )

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
