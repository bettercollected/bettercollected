from common.records import Record

from backend.app.models.template import StandardFormTemplate
import datetime as dt


class FormTemplateDocument(StandardFormTemplate, Record):
    class Settings:
        name = "form_templates"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
