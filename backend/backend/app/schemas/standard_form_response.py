import datetime as dt
from typing import Optional

from common.configs.mongo_document import MongoDocument
from common.models.standard_form import StandardFormResponse


class FormResponseDocument(MongoDocument, StandardFormResponse):
    class Settings:
        name = "form_responses"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
