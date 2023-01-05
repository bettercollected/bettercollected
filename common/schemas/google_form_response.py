import datetime as dt
from typing import Dict, List, Optional

from configs.mongo_document import MongoDocument
from models.google_form_response import GoogleFormResponseDto


class GoogleFormResponseDocument(MongoDocument, GoogleFormResponseDto):
    """
    GoogleFormResponseDocument is a subclass of both MongoDocument and GoogleFormResponseDto. It represents a collection
    of Google Form responses stored in a MongoDB database.

    Attributes:
        dataOwnerFields (List[Dict[str, str | None]], optional): A list of dictionaries containing fields that contain
            data owned by the provider of the Google Form. The dictionaries have keys "name" and "value" representing
            the name and value of the field, respectively.
        dataOwnerIdentifier (str, optional): An identifier for the data owner of the Google Form.
        provider (str, optional): The provider of the Google Form.
        formId (str, optional): The ID of the Google Form.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

    dataOwnerFields: Optional[List[Dict[str, str | None]]] = []
    dataOwnerIdentifier: Optional[str]
    provider: Optional[str]
    formId: Optional[str]

    class Collection:
        name = "formResponses"

    class Settings:
        name = "formResponses"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
