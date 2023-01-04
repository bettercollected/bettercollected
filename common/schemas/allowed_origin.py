import datetime as dt
from configs.mongo_document import MongoDocument


class AllowedOriginsDocument(MongoDocument):
    origin: str

    class Collection:
        name = "allowedOrigins"

    class Settings:
        name = "allowedOrigins"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
