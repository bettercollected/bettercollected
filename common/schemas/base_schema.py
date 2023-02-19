import abc
import datetime as dt
from typing import Optional

from configs.mongo_document import MongoDocument


class BaseDocument(abc.ABC, MongoDocument):
    created_at: Optional[dt.datetime] = dt.datetime.utcnow()
    updated_at: Optional[dt.datetime] = dt.datetime.utcnow()

    class Settings:
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
