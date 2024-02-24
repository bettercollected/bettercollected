import datetime as dt

from beanie import PydanticObjectId
from common.configs.mongo_document import MongoDocument
from pydantic import EmailStr

from backend.app.handlers.database import entity


@entity
class PriceSuggestion(MongoDocument):

    user_id: PydanticObjectId
    email: EmailStr
    price: int

    class Settings:
        name = "price_suggestion"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
