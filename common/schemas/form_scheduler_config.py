import datetime as dt
from typing import Optional

from configs.mongo_document import MongoDocument
from models.form_scheduler_config import FormSchedulerConfigQuery


class SchedulerFormConfigDocument(MongoDocument, FormSchedulerConfigQuery):
    imported_at: Optional[dt.datetime] = dt.datetime.utcnow()

    class Collection:
        name = "schedulerFormConfigs"

    class Settings:
        name = "schedulerFormConfigs"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
