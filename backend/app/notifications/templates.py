from dataclasses import dataclass


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    body: str


_TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "application_submitted": {
        "pl": (
            "Potwierdzenie złożenia wniosku",
            "Dzień dobry {name},\n\notrzymaliśmy Twój wniosek na kierunek {program}. "
            "Status wniosku możesz śledzić w portalu kandydata.\n\nUniwersytet Kalinowski",
        ),
        "en": (
            "Application received",
            "Hello {name},\n\nwe have received your application for {program}. "
            "You can track its status in the applicant portal.\n\nKalinowo University",
        ),
    },
    "decision_accepted": {
        "pl": (
            "Decyzja rekrutacyjna: przyjęcie",
            "Dzień dobry {name},\n\nz przyjemnością informujemy o przyjęciu na kierunek "
            "{program}. Dalsze kroki znajdziesz w portalu kandydata.\n\nUniwersytet Kalinowski",
        ),
        "en": (
            "Admission decision: accepted",
            "Hello {name},\n\nwe are pleased to inform you that you have been admitted to "
            "{program}. Next steps are listed in the applicant portal.\n\nKalinowo University",
        ),
    },
    "decision_rejected": {
        "pl": (
            "Decyzja rekrutacyjna",
            "Dzień dobry {name},\n\nz przykrością informujemy, że Twój wniosek na kierunek "
            "{program} nie został rozpatrzony pozytywnie.\n\nUniwersytet Kalinowski",
        ),
        "en": (
            "Admission decision",
            "Hello {name},\n\nwe regret to inform you that your application for {program} "
            "was not successful.\n\nKalinowo University",
        ),
    },
    "waitlist_promoted": {
        "pl": (
            "Zwolniło się miejsce na zajęciach",
            "Dzień dobry {name},\n\nzwolniło się miejsce i zostałeś(-aś) zapisany(-a) na "
            "zajęcia {course}.\n\nUniwersytet Kalinowski",
        ),
        "en": (
            "A seat became available",
            "Hello {name},\n\na seat became available and you are now enrolled in "
            "{course}.\n\nKalinowo University",
        ),
    },
    "contact_message": {
        "pl": ("Wiadomość z formularza: {subject}", "Od: {name} <{email}>\n\n{message}"),
        "en": ("Contact form message: {subject}", "From: {name} <{email}>\n\n{message}"),
    },
}


def render(template: str, locale: str, context: dict) -> RenderedEmail:
    variants = _TEMPLATES[template]
    subject, body = variants.get(locale, variants["pl"])
    return RenderedEmail(subject=subject.format(**context), body=body.format(**context))
