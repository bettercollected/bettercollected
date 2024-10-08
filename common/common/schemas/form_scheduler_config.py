import datetime as dt
from typing import Optional

from common.configs.mongo_document import MongoDocument

from common.models import FormSchedulerConfigQuery


class SchedulerFormConfigDocument(MongoDocument, FormSchedulerConfigQuery):
    """
    SchedulerFormConfigDocument is a subclass of both MongoDocument and
    FormSchedulerConfigQuery. It represents a collection of form scheduler
    configurations in a MongoDB database.

    Attributes:
    imported_at (datetime, optional): The time that the form scheduler config was imported. Defaults to the current time.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

    imported_at: Optional[dt.datetime] = dt.datetime.now(dt.timezone.utc)

    class Settings:
        name = "scheduler_form_configs"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
