import enum


class FormProvider(str, enum.Enum):
    GOOGLE: str = "google"
    TYPEFORM: str = "typeform"
