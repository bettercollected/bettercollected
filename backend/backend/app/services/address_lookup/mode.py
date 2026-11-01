"""What the two address switches allow.

``ADDRESS_QUESTION_ENABLED`` (the question itself) and ``ADDRESS_LOOKUP_ENABLED``
(the outbound call that fills in street and city) are both off by default. The
lookup works only while both are on: a respondent's form is served with the
question's lookup switched off otherwise (``internal_fields``), the lookup route
answers 404 and no outbound call is made. Read at call time.
"""

from typing import Any

from backend.app.services.new_question_types import address_question_enabled

ADDRESS_TYPE = "address"


def address_lookup_enabled() -> bool:
    """Is the lookup on for this instance (both switches)?"""
    from backend.config import settings

    return address_question_enabled() and bool(
        getattr(settings, "ADDRESS_LOOKUP_ENABLED", False)
    )


def question_looks_up(field: Any) -> bool:
    """Does this address question ask for a lookup: Dutch addresses allowed
    and its own switch not off? (The instance's switches are
    ``address_lookup_enabled``'s.)"""
    properties = getattr(field, "properties", None)
    if isinstance(field, dict):
        properties = field.get("properties")

    def get(key: str) -> Any:
        if isinstance(properties, dict):
            return properties.get(key)
        return getattr(properties, key, None)

    countries = get("countries")
    if countries is not None and "NL" not in countries:
        return False
    return get("address_lookup") is not False
