import datetime as dt
from typing import List, Optional

from beanie import Indexed

from configs.mongo_document import MongoDocument
from enums.roles import Roles
from models.user import UserConnectedServices


class UserDocument(MongoDocument):
    """
    UserDocument is a subclass of MongoDocument. It represents a collection of users stored in a MongoDB database.

    Attributes:
        first_name (str, optional): The first name of the user.
        last_name (str, optional): The last name of the user.
        username (str, optional): The username of the user.
        email (str): The email of the user. This field is indexed and unique.
        roles (List[str]): A list of roles that the user has. Defaults to [Roles.FORM_RESPONDER].
        otp_code (str, optional): The one-time password code for the user.
        otp_expiry (int, optional): The expiration time of the one-time password code in seconds.
        created_at (datetime, optional): The time that the user was created.
        updated_at (datetime, optional): The time that the user was last updated.
        services (List[UserConnectedServices], optional): A list of connected services for the user.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]
    email: Indexed(str, unique=True)
    roles: List[str] = [Roles.FORM_RESPONDER]
    otp_code: Optional[str]
    otp_expiry: Optional[int]
    created_at: Optional[dt.datetime]
    updated_at: Optional[dt.datetime]
    services: Optional[List[UserConnectedServices]]

    class Collection:
        name = "users"

    class Settings:
        name = "users"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
