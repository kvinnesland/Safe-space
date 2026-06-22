"""Norwegian-specific PII recognizers extending Microsoft Presidio."""

import re
from typing import List, Optional

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from .name_lists import NORWEGIAN_NAMES, NORWEGIAN_COMMON_WORDS


def _validate_fodselsnummer(digits: str) -> bool:
    """Validate Norwegian fødselsnummer / D-nummer using mod-11 double checksum."""
    if len(digits) != 11 or not digits.isdigit():
        return False

    day = int(digits[:2])
    month = int(digits[2:4])

    # Accept normal (day 1-31), D-number (day+40), H-number (month+20-32), FH-number (month+40-52)
    valid_day = (1 <= day <= 31) or (41 <= day <= 71)
    valid_month = (1 <= month <= 12) or (21 <= month <= 32) or (41 <= month <= 52)
    if not (valid_day and valid_month):
        return False

    d = [int(c) for c in digits]

    w1 = [3, 7, 6, 1, 8, 9, 4, 5, 2]
    k1 = 11 - (sum(d[i] * w1[i] for i in range(9)) % 11)
    if k1 == 11:
        k1 = 0
    if k1 == 10 or k1 != d[9]:
        return False

    w2 = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    k2 = 11 - (sum(d[i] * w2[i] for i in range(10)) % 11)
    if k2 == 11:
        k2 = 0
    if k2 == 10 or k2 != d[10]:
        return False

    return True


def _validate_org_number(digits: str) -> bool:
    """Validate Norwegian organization number using mod-11 checksum."""
    if len(digits) != 9 or not digits.isdigit():
        return False
    if digits[0] not in "89":
        return False

    weights = [3, 2, 7, 6, 5, 4, 3, 2]
    total = sum(int(digits[i]) * weights[i] for i in range(8))
    check = 11 - (total % 11)
    if check == 11:
        check = 0
    if check == 10:
        return False
    return check == int(digits[8])


class FodselsnummerRecognizer(PatternRecognizer):
    """Recognize Norwegian fødselsnummer (national ID, 11 digits) with checksum validation."""

    PATTERNS = [
        Pattern("Fodselsnummer plain", r"\b(\d{11})\b", 0.85),
        Pattern("Fodselsnummer spaced", r"\b(\d{6}[\s\-]?\d{5})\b", 0.75),
    ]
    CONTEXT = [
        "fnr", "fødselsnummer", "personnummer", "personid",
        "d-nummer", "hnummer", "identifikasjonsnummer",
    ]

    def __init__(self):
        super().__init__(
            supported_entity="NO_FODSELSNUMMER",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="en",
        )

    def validate_result(self, pattern_text: str) -> Optional[bool]:
        digits = re.sub(r"[^\d]", "", pattern_text)
        # True = valid checksum (high confidence); None = uncertain but keep
        # the match — never return False so test/synthetic data isn't silently dropped.
        return True if _validate_fodselsnummer(digits) else None


class OrgNumberRecognizer(PatternRecognizer):
    """Recognize Norwegian organization numbers (9 digits starting with 8 or 9)."""

    PATTERNS = [
        Pattern("OrgNumber formatted", r"\b(\d{3}[\s]\d{3}[\s]\d{3})\b", 0.85),
        Pattern("OrgNumber plain", r"\b([89]\d{8})\b", 0.60),
    ]
    CONTEXT = [
        "organisasjonsnummer", "orgnr", "org.nr", "org nr",
        "foretaksnummer", "virksomhetsnummer", "bedriftsnummer",
        "enhetsregisteret", "brreg",
    ]

    def __init__(self):
        super().__init__(
            supported_entity="NO_ORG_NUMBER",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="en",
        )

    def validate_result(self, pattern_text: str) -> Optional[bool]:
        digits = re.sub(r"[^\d]", "", pattern_text)
        return True if _validate_org_number(digits) else None


class NorwegianPhoneRecognizer(PatternRecognizer):
    """Recognize Norwegian phone numbers (+47, 0047, and local 8-digit formats)."""

    PATTERNS = [
        Pattern("NO phone +47 mobile", r"\+47[\s\-]?[49]\d{7}\b", 0.90),
        Pattern("NO phone +47 landline", r"\+47[\s\-]?[2-8]\d{7}\b", 0.85),
        Pattern("NO phone 0047", r"\b0047[\s\-]?\d{8}\b", 0.90),
        Pattern("NO mobile 8-digit", r"\b([49]\d{2}[\s\-]\d{2}[\s\-]\d{3}|[49]\d{7})\b", 0.70),
        Pattern("NO landline XX XX XX XX", r"\b[2-9]\d[\s\-]\d{2}[\s\-]\d{2}[\s\-]\d{2}\b", 0.60),
    ]
    CONTEXT = [
        "telefon", "tlf", "mobil", "mob", "tel",
        "phone", "mobile", "kontakt", "nummer",
    ]

    def __init__(self):
        super().__init__(
            supported_entity="NO_PHONE",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="en",
        )


class NorwegianBankAccountRecognizer(PatternRecognizer):
    """Recognize Norwegian bank account numbers (XXXX.YY.ZZZZZ format)."""

    PATTERNS = [
        Pattern("NO bank account dotted", r"\b(\d{4}[\.]\d{2}[\.]\d{5})\b", 0.85),
        Pattern("NO bank account spaced", r"\b(\d{4}[\s]\d{2}[\s]\d{5})\b", 0.75),
    ]
    CONTEXT = [
        "kontonummer", "konto", "bankkonto", "bankkontonummer",
        "account", "bank account", "clearing",
    ]

    def __init__(self):
        super().__init__(
            supported_entity="NO_BANK_ACCOUNT",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="en",
        )


class NorwegianHealthInfoRecognizer(PatternRecognizer):
    """Replace medical terminology with [HEALTH_INFO] placeholders.

    Intentionally aggressive: common medical words (diagnose, behandling, etc.)
    are themselves Article 9 indicators and are replaced to prevent the
    surrounding clinical context from revealing the patient's condition.
    """

    PATTERNS = [
        Pattern(
            "NO health keyword",
            r"\b(pasient(?:nummer|id)?|diagnos[ei]|medisiner?|behandling|"
            r"sykehus|helseopplysning|journal(?:nummer)?|resept|"
            r"helsepersonell|innleggelse|poliklinikk|rehabilitering|"
            r"prognose|symptom(?:er)?|operasjon|legemiddel|bivirkninger?)\b",
            0.55,
        ),
    ]
    CONTEXT = [
        "helse", "medisin", "lege", "sykehus", "pasient",
        "diagnose", "behandling", "journal", "resept",
    ]

    def __init__(self):
        super().__init__(
            supported_entity="NO_HEALTH_INFO",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="en",
        )


class NorwegianPostalAddressRecognizer(PatternRecognizer):
    """Recognize Norwegian postal addresses (4-digit postal code + city)."""

    PATTERNS = [
        Pattern(
            "NO postal code",
            r"\b(0[1-9]\d{2}|[1-9]\d{3})\s+[A-ZÆØÅ][a-zæøå]+(?:\s+[A-ZÆØÅ][a-zæøå]+)?\b",
            0.65,
        ),
    ]
    CONTEXT = [
        "adresse", "gateadresse", "postnummer", "poststed",
        "bostedsadresse", "forretningsadresse", "address", "street",
    ]

    def __init__(self):
        super().__init__(
            supported_entity="NO_ADDRESS",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="en",
        )

    def validate_result(self, pattern_text: str) -> Optional[bool]:
        parts = pattern_text.strip().split(maxsplit=1)
        if len(parts) < 2:
            return None
        city = parts[1].strip()
        # ALL-CAPS after a number is an abbreviation (GNR, BNR, TG, ...), not a city
        if city.split()[0].isupper():
            return False
        # If the first city word is a common Norwegian word, it's not a city
        first_word = city.split()[0].lower()
        if first_word in NORWEGIAN_COMMON_WORDS:
            return False
        return None


_MONTHS_NO = (
    "januar|februar|mars|april|mai|juni|juli|"
    "august|september|oktober|november|desember"
)


class NorwegianDateRecognizer(PatternRecognizer):
    """Recognize Norwegian written dates like '14. mars 2024' or '3. juni 2024'."""

    PATTERNS = [
        Pattern(
            "NO date written",
            rf"\b\d{{1,2}}\.?\s+(?:{_MONTHS_NO})(?:\s+\d{{4}})?\b",
            0.65,
        ),
    ]

    def __init__(self):
        super().__init__(
            supported_entity="NO_DATE",
            patterns=self.PATTERNS,
            supported_language="en",
        )


_STREET_SUFFIX_EMBEDDED = (
    "veien|vei|gata|gate|gaten|alléen|allé|plassen|plass"
    "|torget|torg|bakken|terrassen|terrasse|ringen|ring"
    "|stien|sti|svingen|sving|kaia|kai|lien|lia|bryggen|brygge"
    "|løkken|løkka|høyden|brinken"
)
_STREET_SUFFIX_WORD = "allé|gate|gata|vei|plass|torg|brygge|kai|sti|sving|ring"

_CITIES_NO = (
    "Oslo|Bergen|Trondheim|Stavanger|Kristiansand|Tromsø|Drammen|Fredrikstad"
    "|Sandnes|Ålesund|Sarpsborg|Bodø|Sandefjord|Tønsberg|Skien|Porsgrunn"
    "|Arendal|Halden|Hamar|Gjøvik|Lillehammer|Molde|Harstad|Narvik"
    "|Larvik|Kongsberg|Moss|Horten|Alta|Jessheim|Lillestrøm|Asker|Lørenskog"
    "|Levanger|Steinkjer|Namsos|Røros|Kristiansund|Haugesund|Egersund"
    "|Farsund|Mandal|Grimstad|Risør|Askim|Eidsvoll|Hønefoss|Kongsvinger"
    "|Elverum|Brumunddal|Notodden|Stord|Bryne|Orkanger|Stjørdal"
    "|Volda|Ørsta|Åndalsnes|Odda|Jørpeland|Vennesla|Lillesand"
    "|Flekkefjord|Lyngdal|Bamble|Langesund|Tvedestrand|Nittedal|Ski|Rælingen"
)


class NorwegianStreetAddressRecognizer(PatternRecognizer):
    """Recognize Norwegian street addresses like 'Storgata 14' or 'Fjordveien 3B'."""

    PATTERNS = [
        Pattern(
            "NO street embedded suffix",
            rf"\b[A-ZÆØÅ][a-zæøå]*(?:{_STREET_SUFFIX_EMBEDDED})\s+\d+[A-Za-zÆØÅæøå]{{0,2}}\b",
            0.70,
        ),
        Pattern(
            "NO street word suffix",
            rf"\b[A-ZÆØÅ][a-zæøå]+(?:\s+[A-ZÆØÅ][a-zæøå]+)?\s+(?:{_STREET_SUFFIX_WORD})\s+\d+[A-Za-zÆØÅæøå]{{0,2}}\b",
            0.65,
        ),
    ]
    CONTEXT = [
        "adresse", "bosted", "gateadresse", "hjemmeadresse",
        "postadresse", "address", "gate", "vei", "bor", "bopel",
    ]

    def __init__(self):
        super().__init__(
            supported_entity="NO_STREET_ADDRESS",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="en",
        )


class NorwegianPostalCodeRecognizer(PatternRecognizer):
    """Recognize standalone Norwegian postal codes when column/field context confirms it."""

    PATTERNS = [
        Pattern(
            "NO postal code standalone",
            r"\b(0[1-9]\d{2}|[1-9]\d{3})\b",
            0.30,
        ),
    ]
    CONTEXT = ["postnr", "postnummer", "poststed", "postadresse", "postkode", "zip", "postal"]

    def __init__(self):
        super().__init__(
            supported_entity="NO_POSTAL_CODE",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="en",
        )


class NorwegianCityRecognizer(PatternRecognizer):
    """Recognize Norwegian city names when column/field context confirms it."""

    PATTERNS = [
        Pattern(
            "NO city name",
            rf"\b(?:{_CITIES_NO})\b",
            0.30,
        ),
    ]
    CONTEXT = [
        "poststed", "by", "sted", "city", "postnr", "postnummer",
        "adresse", "bosted", "hjemmeadresse", "postadresse",
    ]

    def __init__(self):
        super().__init__(
            supported_entity="NO_CITY",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="en",
        )


class NorwegianHyphenatedNameRecognizer(PatternRecognizer):
    """Catch hyphenated Norwegian first names + surname that NER may only partially tag.

    The Norwegian NER model sometimes creates a span for just the surname when the
    first name contains a hyphen (e.g. 'Bjørn-Arne Haugen' → only 'Haugen' tagged).
    A score of 0.9 ensures this pattern wins conflict resolution over the partial NER hit.
    """

    PATTERNS = [
        Pattern(
            "NO hyphenated first name + surname",
            r"\b[A-ZÆØÅ][a-zæøå]+-[A-ZÆØÅ][a-zæøå]+(?:\s+[A-ZÆØÅ][a-zæøå]+)+\b",
            0.9,
        ),
    ]
    CONTEXT = [
        "navn", "kontakt", "utleier", "leietaker", "stede",
        "referent", "fra", "til", "herr", "fru", "lege", "dr",
    ]

    def __init__(self):
        super().__init__(
            supported_entity="PERSON",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="en",
        )


class NorwegianNameListRecognizer(PatternRecognizer):
    """Detect Norwegian first names and surnames from a curated name list.

    Complements NER by catching names the statistical model misses, especially
    single-word first names that appear without surrounding context.
    Score of 0.6 is intentionally below NER (0.85) so NER wins on conflicts,
    but high enough to survive the 0.4 threshold and appear in results.
    """

    # Build alternation regex from the name list at class definition time.
    # Sort longest-first so the regex engine tries longer matches first.
    _names_sorted = sorted(NORWEGIAN_NAMES, key=len, reverse=True)
    _pattern_str = r"\b(?:" + "|".join(re.escape(n) for n in _names_sorted) + r")\b"

    PATTERNS = [Pattern("NO name list", _pattern_str, 0.6)]
    CONTEXT = [
        "navn", "kontakt", "fra", "til", "herr", "fru",
        "eier", "selger", "kjøper", "leietaker", "utleier",
        "signert", "underskrevet", "attestert", "referent",
        "lege", "megler", "advokat", "revisor",
    ]

    def __init__(self):
        super().__init__(
            supported_entity="PERSON",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="en",
        )

    def validate_result(self, pattern_text: str) -> Optional[bool]:
        # Reject if the matched word is in the common-word denylist
        if pattern_text.strip().lower() in NORWEGIAN_COMMON_WORDS:
            return False
        return None


def get_norwegian_recognizers() -> List[PatternRecognizer]:
    return [
        FodselsnummerRecognizer(),
        OrgNumberRecognizer(),
        NorwegianPhoneRecognizer(),
        NorwegianBankAccountRecognizer(),
        NorwegianHealthInfoRecognizer(),
        NorwegianPostalAddressRecognizer(),
        NorwegianStreetAddressRecognizer(),
        NorwegianPostalCodeRecognizer(),
        NorwegianCityRecognizer(),
        NorwegianDateRecognizer(),
        NorwegianHyphenatedNameRecognizer(),
        NorwegianNameListRecognizer(),
    ]
