import datetime as dt

from common.records import Record
from common.models.standard_form import StandardForm


class FormDocument(Record, StandardForm):
    class Settings:
        name = "forms"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
