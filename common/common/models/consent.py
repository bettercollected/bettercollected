import enum
from typing import Optional

from beanie import PydanticObjectId
from pydantic import BaseModel


class ConsentType(str, enum.Enum):
    INFO = "info"
    CHECKBOX = "checkbox"


class ConsentCategory(str, enum.Enum):
    PURPOSE_OF_THE_FORM = "purpose_of_the_form"
    THIRD_PARTY_INTEGRATIONS = "third_party_integrations"
    DATA_RETENTION = "data_retention"
    RESPONDERS_RIGHTS = "responder_rights"


class ResponseRetentionType(str, enum.Enum):
    DAYS = "days"
    DATE = "date"
    FOREVER = "forever"


class Consent(BaseModel):
    consent_id: Optional[str]
    title: str
    description: Optional[str]
    required: Optional[bool]
    type: ConsentType
    category: ConsentCategory


class ConsentResponse(Consent):
    accepted: Optional[bool]
