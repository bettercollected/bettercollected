import enum


class FormIntegrationType(str, enum.Enum):
    """Enum representing the different form providers that are supported."""

    GOOGLE_SHEET: str = "google_sheet"

