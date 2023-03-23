import enum


class FormProvider(str, enum.Enum):
    """Enum representing the different form providers that are supported."""

    GOOGLE: str = "google"
    TYPEFORM: str = "typeform"

    @classmethod
    def list_providers(cls):
        return [v.value for p, v in cls.__members__.items()]
