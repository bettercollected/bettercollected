import datetime as dt
from typing import Any, Optional

from configs.mongo_document import MongoDocument


class Oauth2CredentialDocument(MongoDocument):
    email: Optional[str]
    state: Optional[str]
    provider: Optional[str]
    credentials: Optional[Any]
    created_at: Optional[dt.datetime]
    updated_at: Optional[dt.datetime]

    class Collection:
        name = "oauth2credentials"

    class Settings:
        name = "oauth2credentials"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
