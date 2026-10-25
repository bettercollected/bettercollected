import datetime as dt
from typing import Optional

from common.models.consent import Consent
from common.records import Record, RecordId


class WorkspaceConsentDocument(Consent, Record):
    workspace_id: Optional[RecordId] = None

    class Settings:
        name = "workspace_consent"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
