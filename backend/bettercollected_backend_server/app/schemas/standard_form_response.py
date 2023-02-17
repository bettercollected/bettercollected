import datetime as dt

from common.configs.mongo_document import MongoDocument
from common.models.standard_form import StandardFormResponseDto


class FormResponseDocument(MongoDocument, StandardFormResponseDto):
    class Collection:
        name = "form_responses"

    class Settings:
        name = "form_responses"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
