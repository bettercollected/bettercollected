import datetime as dt

from common.configs.mongo_document import MongoDocument
from common.models.standard_form import StandardFormDto


class FormDocument(MongoDocument, StandardFormDto):
    class Collection:
        name = "forms"

    class Settings:
        name = "forms"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
