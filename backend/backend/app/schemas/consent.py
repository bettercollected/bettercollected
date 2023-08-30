import datetime as dt
from typing import Optional

from beanie import PydanticObjectId

from backend.app.handlers.database import entity
from common.configs.mongo_document import MongoDocument
from common.models.consent import Consent


@entity
class WorkspaceConsentDocument(Consent, MongoDocument):
    workspace_id: Optional[PydanticObjectId]

    class Settings:
        name = "workspace_consent"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
