import datetime as dt
import enum
from typing import Optional

from beanie import PydanticObjectId
from pydantic import BaseModel

from backend.app.handlers.database import entity
from common.configs.mongo_document import MongoDocument


class ConsentType(str, enum.Enum):
    INFO = "info"
    CHECKBOX = "checkbox"


class ConsentCategory(str, enum.Enum):
    PURPOSE_OF_THE_FORM = "purpose_of_the_form"
    THIRD_PARTY_INTEGRATIONS = "third_party_integrations"
    DATA_RETENTION = "data_retention"
    RESPONDERS_RIGHTS = "responder_rights"


class Consent(BaseModel):
    workspace_id: Optional[PydanticObjectId]
    consent_id: Optional[str]
    title: str
    description: Optional[str]
    required: Optional[bool]
    type: ConsentType
    category: ConsentCategory


class ConsentResponse(Consent):
    accepted: Optional[bool]


@entity
class WorkspaceConsentDocument(Consent, MongoDocument):
    class Settings:
        name = "workspace_consent"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
