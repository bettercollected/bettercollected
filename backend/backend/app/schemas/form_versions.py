import datetime as dt
from typing import Optional

from common.records import Record
from common.models.standard_form import StandardForm


class FormVersionsDocument(Record, StandardForm):
    version: int
    form_id: str
    # the id of the member who published it (None for a version made before
    # this was kept, and for an import's first version)
    published_by: Optional[str] = None

    class Settings:
        name = "form_versions"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
        # (form_id, version) is unique: app revision 0001
