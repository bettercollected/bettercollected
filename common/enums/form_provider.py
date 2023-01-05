import enum


class FormProvider(str, enum.Enum):
    """
    Enum representing the different form providers that are supported.
    """

    GOOGLE: str = "google"
    TYPEFORM: str = "typeform"
