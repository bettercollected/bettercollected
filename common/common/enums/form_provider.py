import enum


class FormProvider(str, enum.Enum):
    """The form providers a live integration exists for (import, proxy, OAuth).

    Stored forms and responses keep their provider as plain text, so forms
    imported from a provider that is no longer listed here (such as Typeform,
    removed in 4.1) stay readable as ordinary forms.
    """

    GOOGLE: str = "google"

    @classmethod
    def list_providers(cls):
        return [v.value for p, v in cls.__members__.items()]
