import os
from functools import lru_cache

try:
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
    from presidio_anonymizer import AnonymizerEngine
    PRESIDIO_AVAILABLE = True
except ImportError:
    AnalyzerEngine = None
    Pattern = None
    PatternRecognizer = None
    RecognizerRegistry = None
    AnonymizerEngine = None
    PRESIDIO_AVAILABLE = False


DEFAULT_PII_ENTITIES = ["PHONE_NUMBER", "EMAIL_ADDRESS"]


def _is_enabled() -> bool:
    return PRESIDIO_AVAILABLE and os.getenv("ENABLE_PII_REDACTION", "false").strip().lower() in {"1", "true", "yes"}


def _entity_types() -> list[str]:
    raw = os.getenv("PII_ENTITIES", "")
    if not raw.strip():
        return DEFAULT_PII_ENTITIES
    return [e.strip() for e in raw.split(",") if e.strip()]


@lru_cache(maxsize=1)
def _analyzer() -> AnalyzerEngine:
    if AnalyzerEngine is None:
        raise RuntimeError("Presidio analyzer is not installed")
    if RecognizerRegistry is None:
        raise RuntimeError("Presidio recognizer registry is not installed")

    # Lightweight mode: use local regex recognizers only (no model/download calls).
    registry = RecognizerRegistry()
    requested = set(_entity_types())

    if PatternRecognizer is None or Pattern is None:
        raise RuntimeError("Presidio pattern recognizers are not installed")

    if "EMAIL_ADDRESS" in requested:
        email_pattern = Pattern(
            name="email_pattern",
            regex=r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            score=0.85,
        )
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="EMAIL_ADDRESS",
                patterns=[email_pattern],
                supported_language="en",
            )
        )

    if "PHONE_NUMBER" in requested:
        phone_pattern = Pattern(
            name="phone_pattern",
            regex=r"(?:\+?\d[\d\s().-]{7,}\d)",
            score=0.75,
        )
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="PHONE_NUMBER",
                patterns=[phone_pattern],
                supported_language="en",
            )
        )

    return AnalyzerEngine(registry=registry, nlp_engine=None, supported_languages=["en"])


@lru_cache(maxsize=1)
def _anonymizer() -> AnonymizerEngine:
    if AnonymizerEngine is None:
        raise RuntimeError("Presidio anonymizer is not installed")
    return AnonymizerEngine()


def detect_pii(text: str) -> list:
    if not _is_enabled() or not text:
        return []
    return _analyzer().analyze(text=text, entities=_entity_types(), language="en")


def anonymize_text(text: str) -> str:
    if not _is_enabled() or not text:
        return text
    findings = detect_pii(text)
    if not findings:
        return text
    result = _anonymizer().anonymize(text=text, analyzer_results=findings)
    return result.text
