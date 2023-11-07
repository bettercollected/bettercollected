from common.configs.mongo_document import MongoDocument

from backend.app.handlers.database import entity
from backend.app.models.template import StandardFormTemplate
import datetime as dt


@entity
class FormTemplateDocument(StandardFormTemplate, MongoDocument):
    class Settings:
        name = "form_templates"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
