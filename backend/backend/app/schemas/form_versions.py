import datetime as dt

import pymongo
from pymongo import IndexModel

from backend.app.handlers.database import entity
from common.configs.mongo_document import MongoDocument
from common.models.standard_form import StandardForm


@entity
class FormVersionsDocument(MongoDocument, StandardForm):
    version: int
    form_id: str

    class Settings:
        name = "form_versions"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
        indexes = [
            IndexModel([("form_id", pymongo.DESCENDING), ("version", pymongo.DESCENDING)], unique=True)
        ]
