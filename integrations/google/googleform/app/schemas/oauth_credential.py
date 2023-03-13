import datetime as dt
from typing import Any, Optional

from common.schemas.base_schema import BaseDocument
from googleform.app.models.oauth_credential import GoogleCredentialResponse
from googleform.app.services.database_service import entity


@entity
class Oauth2CredentialDocument(BaseDocument):
    """
    Oauth2CredentialDocument is a subclass of MongoDocument. It represents a collection of OAuth2 credentials stored
    in a MongoDB database.

    Attributes:
        email (str, optional): The email associated with the OAuth2 credentials.
        state (str, optional): The state associated with the OAuth2 credentials.
        provider (str, optional): The provider of the OAuth2 credentials.
        credentials (Any, optional): The OAuth2 credentials.
        created_at (datetime, optional): The time that the OAuth2 credentials were created.
        updated_at (datetime, optional): The time that the OAuth2 credentials were last updated.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

    email: Optional[str]
    state: Optional[str]
    provider: Optional[str]
    credentials: Optional[GoogleCredentialResponse]
