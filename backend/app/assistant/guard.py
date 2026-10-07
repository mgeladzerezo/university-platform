import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Covers PESEL (11 digits), phone numbers and document numbers.
_LONG_NUMBER = re.compile(r"\+?\d(?:[\s-]?\d){6,}")

_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts?)",
        r"disregard\s+(all\s+|any\s+)?(previous|prior|above|your)\s+(instructions|rules)",
        r"(reveal|show|print|repeat)\b.{0,40}\b(system|hidden|initial)\s+(prompt|instructions)",
        r"\bsystem\s+prompt\b",
        r"\byou\s+are\s+now\b",
        r"\b(developer|dan|jailbreak)\s+mode\b",
        r"zignoruj\s+(wszystkie\s+)?(poprzednie|powyższe|powyzsze|wcześniejsze|wczesniejsze)",
        r"(pokaż|pokaz|ujawnij|wypisz)\b.{0,40}\b(prompt|instrukcj)",
        r"jesteś\s+teraz|jestes\s+teraz",
    )
]


def redact_pii(text: str) -> str:
    """Remove contact details and long identifiers a visitor may have typed in."""
    return _LONG_NUMBER.sub("[redacted]", _EMAIL.sub("[redacted]", text))


def looks_like_injection(text: str) -> bool:
    """Cheap first filter for obvious attempts.

    The real defence is structural: the model gets no tools, no personal data and
    only published text, so a bypass of this filter has nothing sensitive to reach.
    """
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)
