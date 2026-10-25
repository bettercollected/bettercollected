import datetime as dt

from common.records import Record
from common.models.standard_form import StandardForm


class FormVersionsDocument(Record, StandardForm):
    version: int
    form_id: str

    class Settings:
        name = "form_versions"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
        # (form_id, version) is unique: app revision 0001
