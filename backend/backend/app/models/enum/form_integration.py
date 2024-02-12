import enum


class FormIntegrationType(str, enum.Enum):
    """Enum representing the different form providers that are supported."""

    GOOGLE_SHEET: str = "integrate_google_sheets"


class FormActionType(str, enum.Enum):
    INTERNAL: str = "Internal"
    EXTERNAL: str = "External"
