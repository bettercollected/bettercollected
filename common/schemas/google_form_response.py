import datetime as dt
from typing import Dict, List, Optional

from configs.mongo_document import MongoDocument
from models.google_form_response import GoogleFormResponseDto


class GoogleFormResponseDocument(MongoDocument, GoogleFormResponseDto):
    dataOwnerFields: Optional[List[Dict[str, str | None]]] = []
    dataOwnerIdentifier: Optional[str]
    provider: Optional[str]
    formId: Optional[str]

    class Collection:
        name = "formResponses"

    class Settings:
        name = "formResponses"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
