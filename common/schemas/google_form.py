import datetime as dt
from typing import List, Optional

from configs.mongo_document import MongoDocument
from models.google_form import GoogleFormDto


class GoogleFormDocument(MongoDocument, GoogleFormDto):
    provider: Optional[str]
    dataOwnerFields: Optional[List[str]] = []

    class Collection:
        name = "forms"

    class Settings:
        name = "forms"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
