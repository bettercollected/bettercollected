import datetime as dt
from typing import List, Optional

from common.configs.mongo_document import MongoDocument
from googleform.app.models.google_form import GoogleFormDto


class GoogleFormDocument(MongoDocument, GoogleFormDto):
    """
    GoogleFormDocument is a subclass of both MongoDocument and GoogleFormDto. It represents a collection of Google
    Forms stored in a MongoDB database.

    Attributes:
        provider (str, optional): The provider of the Google Form.
        dataOwnerFields (List[str], optional): A list of fields that contain data owned by the provider of the Google Form.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

    provider: Optional[str]
    dataOwnerFields: Optional[List[str]] = []

    class Collection:
        name = "forms"

    class Settings:
        name = "forms"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
