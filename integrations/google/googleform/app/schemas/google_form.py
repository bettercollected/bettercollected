import datetime as dt
from typing import List, Optional

from common.schemas.base_schema import BaseDocument
from googleform.app.models.google_form import GoogleFormDto
from googleform.app.services.database_service import entity


@entity
class GoogleFormDocument(BaseDocument, GoogleFormDto):
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
